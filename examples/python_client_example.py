"""Local example: submit a sample signal to a running MT5 Execution Bridge instance.

Assumes the bridge is running with DRY_RUN=true. This example makes no claims
about trading profitability -- it only demonstrates the client/API contract.
"""

from datetime import UTC, datetime

from client.bridge_client import MT5ExecutionBridgeClient


def main() -> None:
    client = MT5ExecutionBridgeClient()

    print("Health:", client.health())
    print("Status:", client.status())

    signal_id = f"example-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
    result = client.send_signal(
        signal_id=signal_id,
        symbol="EURUSD",
        action="BUY",
        risk_percent=0.5,
        stop_loss=1.0850,
        take_profit=1.0950,
        strategy="example",
    )
    print("Submitted:", result)

    status = client.get_signal(signal_id)
    print("Signal status:", status)


if __name__ == "__main__":
    main()
