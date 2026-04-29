import logging
import os
import socket
import time
import uuid
from typing import List, Optional, Tuple

import azure.functions as func
from applicationinsights import TelemetryClient
from applicationinsights.channel import SynchronousQueue, SynchronousSender, TelemetryChannel
from applicationinsights.channel.contracts import AvailabilityData

app = func.FunctionApp()


# Lee una variable de entorno y la divide por ";" para obtener una lista de valores.
# Ejemplo: "host1;host2;host3" -> ["host1", "host2", "host3"]
def _get_env_list(name: str) -> List[str]:
	raw = os.getenv(name, "")
	return [item.strip() for item in raw.split(";") if item.strip()]


# Construye y retorna un cliente de telemetría de Application Insights.
# Usa la clave de instrumentación desde la variable de entorno APPINSIGHTS_INSTRUMENTATIONKEY.
# Si la clave no está configurada, retorna None y la telemetría se omite.
def _build_telemetry_client() -> Optional[TelemetryClient]:
	instrumentation_key = os.getenv("APPINSIGHTS_INSTRUMENTATIONKEY", "").strip()
	if not instrumentation_key:
		logging.warning("APPINSIGHTS_INSTRUMENTATIONKEY is not set. Telemetry will be skipped.")
		return None

	sender = SynchronousSender()
	queue = SynchronousQueue(sender)
	channel = TelemetryChannel(None, queue)
	return TelemetryClient(instrumentation_key, telemetry_channel=channel)


# Envía un registro de disponibilidad (availability) a Application Insights.
# Registra el nombre de la prueba, si fue exitosa, la duración en ms,
# la ubicación de ejecución y un mensaje descriptivo del resultado.
# Si el cliente de telemetría es None, no hace nada.
def _ms_to_duration(duration_ms: int) -> str:
	"""Converts milliseconds to the Application Insights duration format (dd.hh:mm:ss.mmm)."""
	ms = duration_ms % 1000
	seconds = (duration_ms // 1000) % 60
	minutes = (duration_ms // 60000) % 60
	hours = (duration_ms // 3600000) % 24
	days = duration_ms // 86400000
	if days:
		return '%d.%02d:%02d:%02d.%03d' % (days, hours, minutes, seconds, ms)
	return '%02d:%02d:%02d.%03d' % (hours, minutes, seconds, ms)


def _send_availability(
	client: Optional[TelemetryClient],
	name: str,
	success: bool,
	duration_ms: int,
	run_location: str,
	message: str,
) -> None:
	if client is None:
		return

	try:
		data = AvailabilityData()
		data.id = str(uuid.uuid4())
		data.name = name
		data.duration = _ms_to_duration(duration_ms)
		data.success = success
		data.run_location = run_location
		data.message = message

		client.track(data, client._context)
		client.flush()
	except Exception:
		logging.exception("Failed to track availability for %s", name)


# Realiza una verificación de resolución DNS para un hostname dado.
# Retorna una tupla con: (éxito: bool, duración en ms: int, mensaje: str).
# En caso exitoso, devuelve las IPs resueltas; en caso de fallo, el error.
def dns_check(hostname: str) -> Tuple[bool, int, str]:
	start = time.perf_counter()
	try:
		addr_info = socket.getaddrinfo(hostname, None)
		duration_ms = int((time.perf_counter() - start) * 1000)

		unique_ips = sorted({item[4][0] for item in addr_info if item and item[4]})
		if not unique_ips:
			return False, duration_ms, f"DNS lookup returned no addresses for {hostname}"

		return True, duration_ms, f"Resolved IPs: {', '.join(unique_ips)}"
	except Exception as ex:
		duration_ms = int((time.perf_counter() - start) * 1000)
		return False, duration_ms, f"DNS error: {ex}"


# Realiza una verificación de conectividad TCP hacia un host y puerto específicos.
# Intenta establecer una conexión TCP con un timeout configurable (por defecto 3 segundos).
# Retorna una tupla con: (éxito: bool, duración en ms: int, mensaje: str).
def tcp_check(host: str, port: int, timeout_seconds: float = 3.0) -> Tuple[bool, int, str]:
	start = time.perf_counter()
	endpoint = f"{host}:{port}"
	try:
		with socket.create_connection((host, port), timeout=timeout_seconds):
			pass
		duration_ms = int((time.perf_counter() - start) * 1000)
		return True, duration_ms, f"TCP connectivity succeeded to {endpoint}"
	except Exception as ex:
		duration_ms = int((time.perf_counter() - start) * 1000)
		return False, duration_ms, f"TCP error to {endpoint}: {ex}"


# Función principal de Azure Functions que se ejecuta según un cronograma (timer trigger).
# Lee los destinos DNS y TCP desde variables de entorno (DNS_TARGETS y TCP_TARGETS),
# ejecuta las pruebas de conectividad para cada uno, registra los resultados en logs
# y envía métricas de disponibilidad a Application Insights.
@app.timer_trigger(schedule="%TIMER_SCHEDULE%", arg_name="mytimer", use_monitor=False)
def connectivity_monitor(mytimer: func.TimerRequest) -> None:
	run_location = os.getenv("RUN_LOCATION", "Unknown")
	dns_targets = _get_env_list("DNS_TARGETS")
	tcp_targets = _get_env_list("TCP_TARGETS")
	telemetry_client = _build_telemetry_client()

	if mytimer.past_due:
		logging.warning("Timer trigger is running later than scheduled.")

	if not dns_targets and not tcp_targets:
		logging.warning("No targets configured. Set DNS_TARGETS and/or TCP_TARGETS.")
		return

	for hostname in dns_targets:
		success, duration_ms, message = dns_check(hostname)
		event_name = f"DNS::{hostname}"

		if success:
			logging.info("%s | %d ms | %s", event_name, duration_ms, message)
		else:
			logging.warning("%s | %d ms | %s", event_name, duration_ms, message)

		_send_availability(
			client=telemetry_client,
			name=event_name,
			success=success,
			duration_ms=duration_ms,
			run_location=run_location,
			message=message,
		)

	for target in tcp_targets:
		if ":" not in target:
			logging.error("Invalid TCP target format '%s'. Expected host:port", target)
			continue

		host, port_raw = target.rsplit(":", 1)
		host = host.strip()

		try:
			port = int(port_raw.strip())
			if port < 1 or port > 65535:
				raise ValueError("Port out of valid range")
		except ValueError:
			logging.error("Invalid TCP port in target '%s'. Expected integer 1-65535", target)
			continue

		success, duration_ms, message = tcp_check(host, port)
		event_name = f"TCP::{host}:{port}"

		if success:
			logging.info("%s | %d ms | %s", event_name, duration_ms, message)
		else:
			logging.warning("%s | %d ms | %s", event_name, duration_ms, message)

		_send_availability(
			client=telemetry_client,
			name=event_name,
			success=success,
			duration_ms=duration_ms,
			run_location=run_location,
			message=message,
		)
