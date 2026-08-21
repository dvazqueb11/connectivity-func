import logging
import os
import socket
import time
from typing import Callable, List, Optional, Tuple

import azure.functions as func
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import metrics, trace
from opentelemetry.trace import SpanKind, Status, StatusCode

app = func.FunctionApp()


def _configure_telemetry() -> None:
	worker_telemetry_enabled = os.getenv(
		"PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY", ""
	).strip().lower() == "true"
	if worker_telemetry_enabled:
		return

	connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
	if not connection_string:
		logging.warning(
			"APPLICATIONINSIGHTS_CONNECTION_STRING is not set. Telemetry will be skipped."
		)
		return

	try:
		configure_azure_monitor(connection_string=connection_string)
	except Exception:
		logging.exception("Failed to configure Azure Monitor OpenTelemetry.")


_configure_telemetry()

_tracer = trace.get_tracer("connectivity_monitor")
_meter = metrics.get_meter("connectivity_monitor")
_check_counter = _meter.create_counter(
	"connectivity.check.count",
	unit="{check}",
	description="Number of DNS and TCP connectivity checks.",
)
_check_duration = _meter.create_histogram(
	"connectivity.check.duration",
	unit="ms",
	description="Duration of DNS and TCP connectivity checks.",
)


# Lee una variable de entorno y la divide por ";" para obtener una lista de valores.
# Ejemplo: "host1;host2;host3" -> ["host1", "host2", "host3"]
def _get_env_list(name: str) -> List[str]:
	raw = os.getenv(name, "")
	return [item.strip() for item in raw.split(";") if item.strip()]


def _run_observed_check(
	name: str,
	check_type: str,
	target: str,
	host: str,
	run_location: str,
	check: Callable[[], Tuple[bool, int, str]],
	port: Optional[int] = None,
) -> None:
	span_attributes = {
		"connectivity.check.type": check_type,
		"connectivity.target": target,
		"connectivity.run.location": run_location,
		"server.address": host,
	}
	if port is not None:
		span_attributes["server.port"] = port
		span_attributes["network.transport"] = "tcp"

	with _tracer.start_as_current_span(
		name,
		kind=SpanKind.CLIENT,
		attributes=span_attributes,
	) as span:
		success, duration_ms, message = check()
		span.set_attributes(
			{
				"connectivity.success": success,
				"connectivity.duration_ms": duration_ms,
				"connectivity.message": message,
			}
		)
		if success:
			span.set_status(Status(StatusCode.OK))
		else:
			span.set_status(Status(StatusCode.ERROR, message))
			span.set_attribute("error.type", "connectivity_check_failed")

		metric_attributes = {
			"connectivity.check.type": check_type,
			"connectivity.target": target,
			"connectivity.run.location": run_location,
			"connectivity.success": success,
		}
		_check_counter.add(1, metric_attributes)
		_check_duration.record(duration_ms, metric_attributes)

	if success:
		logging.info("%s | %d ms | %s", name, duration_ms, message)
	else:
		logging.warning("%s | %d ms | %s", name, duration_ms, message)


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

	if mytimer.past_due:
		logging.warning("Timer trigger is running later than scheduled.")

	if not dns_targets and not tcp_targets:
		logging.warning("No targets configured. Set DNS_TARGETS and/or TCP_TARGETS.")
		return

	for hostname in dns_targets:
		event_name = f"DNS::{hostname}"
		_run_observed_check(
			name=event_name,
			check_type="dns",
			target=hostname,
			host=hostname,
			run_location=run_location,
			check=lambda hostname=hostname: dns_check(hostname),
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

		event_name = f"TCP::{host}:{port}"
		_run_observed_check(
			name=event_name,
			check_type="tcp",
			target=f"{host}:{port}",
			host=host,
			run_location=run_location,
			check=lambda host=host, port=port: tcp_check(host, port),
			port=port,
		)
