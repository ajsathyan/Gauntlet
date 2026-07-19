"""Compatibility-free command-family configuration helpers."""


def configure_runtime(*, configure_closeout, configure_land, configure_merge, print_payload):
    """Inject the one shared presentation dependency used by generic workflows."""

    configure_closeout(print_payload=print_payload)
    configure_land(print_payload=print_payload)
    configure_merge(print_payload=print_payload)
