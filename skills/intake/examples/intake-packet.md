# Intake Packet Example

- Goal and accepted scope: show each provisioned machine's existing stable label in the private dashboard list.
- Affected behavior: list rows and their loading state; provisioning stays unchanged because the user explicitly said to preserve it.
- Observable done behavior and proof: representative rows remain distinguishable before and after refresh; a fixture with two similar machines fails if labels are hidden.
- Constraint: use existing label data.
- Cannot verify: whether every provider supplies a stable label; inspect representative provider payloads.
- First implementation step: trace the existing label from payload to row rendering.
