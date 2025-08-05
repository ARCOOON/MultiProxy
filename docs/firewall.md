# Firewall and Shell Documentation

This document describes the three built‑in plugins that implement an enterprise‑grade firewall for the proxy server: **Firewall**, **FirewallConfig** and **FirewallShell**.  Together they provide robust traffic filtering, persistent configuration and an interactive management interface reminiscent of Cisco hardware.

## Firewall Plugin

The `Firewall` plugin is the enforcement engine.  It maintains an ordered list of **rules** that determine whether an incoming request is allowed or denied.  Each rule is a dictionary with the following keys:

| Key     | Description                                                              |
|--------:|---------------------------------------------------------------------------|
| `action` | Required.  Either `allow` or `deny`.  Determines the disposition when the rule matches. |
| `ip`     | Optional.  A single IP or CIDR network (e.g. `192.168.0.1/32`).  Matches based on the client’s source address. |
| `method` | Optional.  HTTP method to match (e.g. `GET`, `POST`).  Case insensitive. |
| `host`   | Optional.  Hostname from the `Host` header.  Can include a port but the match is performed on the hostname alone. |
| `path`   | Optional.  URL path prefix.  The request’s path must start with this value. |

Rules are evaluated in order; the first rule whose conditions all match will either permit or block the request based on its `action`.  If no rule matches, the firewall defaults to **allow**.

Example rules:

```yaml
rules:
  - action: deny
    ip: "10.0.0.0/8"
    description: "Block internal network"
  - action: allow
    method: GET
    path: "/public"
    description: "Allow public GET requests"
```

In this configuration requests originating from the 10.0.0.0/8 network are denied outright.  GET requests to `/public` are allowed.  Everything else is permitted because there is no explicit deny.

### API

The firewall plugin exposes several methods that can be consumed by other plugins or the CLI:

* `get_rules() -> list` – returns a copy of the current rule list.
* `set_rules(rules: list)` – replaces the rule list with the provided value.
* `add_rule(rule: dict, index: Optional[int] = None)` – appends the rule or inserts it at a specific index.
* `remove_rule(index: int)` – deletes the rule at the given position.
* `clear_rules()` – removes all rules.

Use these methods to manipulate firewall state programmatically.

## FirewallConfig Plugin

The `FirewallConfig` plugin persists firewall rules to a YAML file and restores them on startup.  By default it looks for a file named `config.yaml` in the proxy package directory, but you can specify a different path when constructing the proxy server or via the CLI.

### Loading and Saving

Use the following CLI commands from the shell (see below) to manage the configuration:

* `load-config [filename]` – read the specified YAML file and apply its rules to the firewall.  If `filename` is omitted the plugin’s configured default is used.
* `save-config [filename]` – write the current firewall rules to the specified file.  Again, if omitted the default filename is used.
* `reset-config` – clear all rules from the firewall (does not touch the file).

Internally the plugin uses `yaml.safe_load` and `yaml.safe_dump` from PyYAML.  The YAML structure is expected to have a top‑level `rules` key containing a list of rule objects as shown in the example above.

## FirewallShell Plugin

Managing a firewall through JSON or Python APIs can be tedious.  To provide a more ergonomic experience, the `FirewallShell` plugin offers an interactive command‑line interface inspired by Cisco IOS.  Launch the shell with:

```bash
python -m proxy.shell
```

### Exec Mode

Upon starting the shell you are placed in **exec mode** (indicated by the `#` prompt).  Available commands include:

* `show firewall rules` – display the current firewall rule set.  Each rule is numbered and printed in its raw dictionary form.
* `configure terminal` (or `conf t`) – enter configuration mode to modify rules.
* `write memory` (or `wr mem`) – save the current rules via the `FirewallConfig` plugin to the configured YAML file.
* `help` or `?` – display a summary of available commands.

### Configuration Mode

In configuration mode the prompt changes to `(config)#`.  Here you can add and remove rules:

* `rule add <allow|deny> [key=value …]` – append a new rule.  The first argument is the action; subsequent arguments are key/value pairs such as `ip=192.168.1.0/24`, `method=POST`, `path=/admin`.  Example:

  ```
  rule add deny ip=172.16.0.0/12 path=/secret
  ```

  This command denies any request from the 172.16.0.0/12 network to paths starting with `/secret`.

* `rule del <index>` – remove the rule at the given index.  Use `show firewall rules` to see the indices.

* `exit` – leave configuration mode and return to exec mode.

Changes made in configuration mode are applied immediately but are not saved to disk until you run `write memory`.  This separation mirrors the running vs. startup configuration concept in networking devices.

## Putting It All Together

1. **Start the proxy server**:

   ```bash
   python -m proxy.server --listen 127.0.0.1:8080
   ```

2. **Configure your HTTP client** to use `http://127.0.0.1:8080` as its proxy.

3. **Launch the shell** in another terminal:

   ```bash
   python -m proxy.shell
   ```

4. **Inspect and edit rules** using the commands above.  Try adding a rule to block a specific path or IP range, then visit a site through the proxy to see it enforced.

5. **Save your configuration** with `write memory`.  The rules will be written to `config.yaml` and reloaded automatically the next time the proxy starts.

These plugins provide a robust foundation for controlling traffic through the proxy.  Feel free to extend them or write your own plugins to meet your organisation’s security policies.