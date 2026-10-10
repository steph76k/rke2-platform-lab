# Security templates

Source: OpenSearch Security tag `3.9.0.0`, directory `config/`:
https://github.com/opensearch-project/security/tree/3.9.0.0/config

Modified for this lab: comments and YAML formatting normalized; `config.yml`
reduced to internal Basic authentication and `roles_mapping.yml` reduced to the
admin and Dashboards mappings. `internal_users.yml` is generated in memory by the
approved bootstrap, never stored here. Other role definitions retain upstream
semantics. License and attribution are in LICENSE.txt and NOTICE.txt.

The `allow_default_init_securityindex` behavior and configuration directory were
checked against the same tag's ConfigurationRepository.java. Runtime acceptance
still requires the approved fresh-cluster test described in docs/validation.md.
