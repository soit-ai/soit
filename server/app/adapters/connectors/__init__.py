"""Knowledge connector implementations.

Each connector reads one kind of external system and reaches the network only
through the governed egress client. The contract they implement lives in
``app.kernel.ports.connectors``; ``app.wiring.connectors`` registers them.
"""
