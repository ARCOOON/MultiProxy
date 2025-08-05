# Python Proxy Server with Modular Plugin System

This repository contains a modular HTTP proxy server built with Python 3.12. It is designed to run locally and to be extended through a simple plugin system. Three built‑in plugins provide enterprise‑grade firewall capabilities, configuration persistence via YAML, and a Cisco‑inspired command shell.

## Features

- **Plugin architecture** – Plugins are Python classes that derive from a common base class. They are discovered at startup from the built‑in `proxy.plugins` package and from an optional external plugins directory. Each plugin can hook into request and response events and expose its own CLI commands.
- **Enterprise firewall** – The `Firewall` plugin allows you to define granular rules to allow or block requests based on client IP addresses, HTTP methods, hosts or URL paths. The default behaviour is to permit all traffic unless a matching deny rule is encountered.
- **Persistent configuration** – The `FirewallConfig` plugin builds on top of the firewall to load and save rule sets to a YAML file. Administrators can persist their policies across restarts and version control them along with other infrastructure code.
- **Interactive shell** – The `FirewallShell` plugin offers a command‑line interface that emulates the feel of Cisco networking equipment. Operators can show, add, delete and reorder rules using commands such as `show firewall rules`, `config terminal`, `rule add …` etc. The shell runs as a separate process that connects to the proxy via the plugin manager.
- - **Asynchronous HTTP(S) proxy** supporting:
  * Full HTTP/1.1 proxying with request/response hooks via plugins
  * **HTTPS** & **generic TCP/IP** tunneling via `CONNECT`
  * **WebSocket** upgrade detection & raw frame proxying

## Layout

```
MultiProxy/
├── README.md              – project overview and documentation
├── src/
│   └── proxy/
│       ├── __init__.py     – package initialisation
│       ├── server.py       – core HTTP proxy implementation
│       ├── plugin_base.py  – abstract base class for plugins
│       ├── plugin_manager.py – loads and manages plugins
│       ├── config.yaml     – example YAML file for firewall rules
│       ├── shell.py        – entry point for the interactive CLI
│       └── plugins/
│           ├── __init__.py
│           ├── firewall.py       – enterprise firewall plugin
│           ├── firewall_config.py – saves and loads firewall rules from YAML
│           └── firewall_shell.py  – interactive Cisco‑style shell
└── docs/
    ├── plugin_system.md    – detailed guide on writing plugins
    └── firewall.md         – firewall plugin design and usage
```

## Getting Started

1. **Install dependencies**

   The only external dependency is **PyYAML** for reading/writing YAML configuration files. It is already included in this environment, but on a fresh system you can install it with:

   ```bash
   pip install pyyaml
   ```

2. **Run the proxy server**

   Start the proxy on port 8080 (or any port of your choosing) with:

   ```bash
   python -m proxy.server --listen 0.0.0.0:8080
   ```

   You can then configure your web browser or application to use `http://localhost:8080` as its HTTP proxy. Note that HTTPS tunnelling (`CONNECT`) is not implemented for brevity.

3. **Interact via the shell**

   Launch the Cisco‑style shell from a separate terminal:

   ```bash
   python -m proxy.shell
   ```

   Use the `help` command to discover available commands. For example:

   - `show firewall rules` — list all firewall rules in order.
   - `config terminal` — enter configuration mode and add or delete rules.
   - `save` — persist current rules to `config.yaml` via the `FirewallConfig` plugin.

4. **Extending the proxy**

   Read the documentation in `docs/plugin_system.md` to learn how to implement your own plugins. By placing additional modules into a `plugins` directory and exporting a `Plugin` class, your custom logic will be loaded automatically at startup.

## Support

This project is a proof of concept and is not hardened for production use. Contributions and feedback are welcome. For further details on the firewall logic and CLI, consult the documentation in the `docs` folder.
