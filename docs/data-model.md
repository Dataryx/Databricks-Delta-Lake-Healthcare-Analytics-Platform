# Data model

Silver contracts define typed entities under config/contracts/.
Gold follows a Kimball layout (dimensions, facts, marts) described in docs/gold.md
and ADR 0006.

Use table comments and the contract YAML as the source of truth for grain.
