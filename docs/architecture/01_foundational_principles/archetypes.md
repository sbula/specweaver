# Archetypes

| Archetype | Allowed | Forbidden |
|-----------|---------|-----------|
| `pure-logic` | Business logic, calculations, value objects | DB, HTTP, I/O, framework imports |
| `adapter` | Framework wrappers, external library integration | Direct business logic |
| `facade` | Thin delegation, method signatures | Implementation logic, complex helpers |
| `contract` | Interfaces, Protocols, DTOs, constants | Any implementation code |
| `orchestrator` | Workflow coordination, event routing, pipeline assembly | Direct data transformation |
| `data` | Static resources, config files, templates | Code with behavior |

See [context_yaml_spec.md](../03_system_topology/context_yaml_spec.md) for the full archetype specification.
