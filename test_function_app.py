import os
import unittest
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

os.environ["PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY"] = "true"

import function_app
from opentelemetry.trace import SpanKind, StatusCode


class FakeSpan:
	def __init__(self, attributes):
		self.attributes = dict(attributes)
		self.status = None

	def set_attributes(self, attributes):
		self.attributes.update(attributes)

	def set_attribute(self, name, value):
		self.attributes[name] = value

	def set_status(self, status):
		self.status = status


class FakeTracer:
	def __init__(self):
		self.kind = None
		self.name = None
		self.span = None

	def start_as_current_span(self, name, kind, attributes):
		self.name = name
		self.kind = kind
		self.span = FakeSpan(attributes)
		return nullcontext(self.span)


class ObservedCheckTests(unittest.TestCase):
	def test_failed_tcp_check_records_span_and_metrics(self):
		tracer = FakeTracer()
		counter = MagicMock()
		duration = MagicMock()

		with (
			patch.object(function_app, "_tracer", tracer),
			patch.object(function_app, "_check_counter", counter),
			patch.object(function_app, "_check_duration", duration),
		):
			function_app._run_observed_check(
				name="TCP::example.com:443",
				check_type="tcp",
				target="example.com:443",
				host="example.com",
				run_location="East US",
				check=lambda: (False, 125, "connection refused"),
				port=443,
			)

		self.assertEqual(tracer.name, "TCP::example.com:443")
		self.assertEqual(tracer.kind, SpanKind.CLIENT)
		self.assertEqual(tracer.span.status.status_code, StatusCode.ERROR)
		self.assertEqual(tracer.span.attributes["server.address"], "example.com")
		self.assertEqual(tracer.span.attributes["server.port"], 443)
		self.assertEqual(tracer.span.attributes["connectivity.success"], False)
		self.assertEqual(
			tracer.span.attributes["error.type"], "connectivity_check_failed"
		)
		counter.add.assert_called_once()
		duration.record.assert_called_once()
		self.assertEqual(duration.record.call_args.args[0], 125)


if __name__ == "__main__":
	unittest.main()