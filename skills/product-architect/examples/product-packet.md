# Product Packet Example

- Mode recommendation: Feature
- Primary user and situation: analyst saving a repeated search
- User job: return to a useful query quickly
- First-value moment: saved search appears and can be reopened
- Workflow: search, save, name, reopen, delete
- Information architecture: saved searches live beside recent searches
- Key screens or states: empty, saved, duplicate name, delete confirm
- Key states not in scope: team sharing
- Meaningful metrics: save success rate, because it shows completion
- Not relevant because: retention emails and sharing stretch scope
- Trust/privacy: saved query may contain sensitive terms
- Configuration requirements: query retention is operator-configured; stable duplicate-name behavior remains in code
- PM acceptance: save/reopen/delete works
- Design acceptance: empty and error states are clear
- Cannot verify: analytics event names
