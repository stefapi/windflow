# Plugins Documentation

This document provides comprehensive information about the plugin system in the Windflow project, including plugin architecture, available plugins, and examples of plugin usage.

## Plugin Architecture

Windflow uses a plugin-based architecture to extend its functionality. Plugins are self-contained modules that can be added to the platform to provide additional features, deployment options, or integrations.

### Plugin Structure

Each plugin follows a standard directory structure:

```
plugin-name/
├── config/           # Configuration files and schemas
├── hooks/            # Lifecycle hooks for plugin events
├── scripts/          # Utility scripts for the plugin
├── plugin.yml        # Plugin metadata and configuration
└── README.md         # Plugin documentation
```

Additional directories may be present depending on the plugin type:

- `build/`: For plugins that require build materials
- `compose/`: For plugins that use Docker Compose

### Plugin Metadata

Each plugin must include a `plugin.yml` file that defines its metadata, configuration schema, and dependencies. This file is used by the platform to register and manage the plugin.

Example `plugin.yml`:

```yaml
name: example-plugin
version: 1.0.0
description: An example plugin for Windflow
author: Windflow Team
license: MIT

dependencies:
  - core: ">=1.0.0"
  - database: ">=2.0.0"

config:
  schema: config/schema.json
  defaults: config/defaults.yaml

hooks:
  pre-deploy: hooks/pre-deploy.sh
  post-deploy: hooks/post-deploy.sh
  pre-upgrade: hooks/pre-upgrade.sh
  post-upgrade: hooks/post-upgrade.sh
```

### Plugin Lifecycle

Plugins can hook into various lifecycle events of the platform:

1. **Installation**: When the plugin is first installed
2. **Deployment**: When the plugin is deployed to an environment
3. **Upgrade**: When the plugin is upgraded to a new version
4. **Removal**: When the plugin is removed from the platform

Each lifecycle event can have pre- and post-event hooks that are executed by the platform.

### Plugin Configuration

Plugins can define their configuration schema using JSON Schema. This schema is used to validate the configuration provided by the user. Default configuration values can be provided in a `defaults.yaml` file.

## Available Plugins

### Template Plugin

The Template Plugin serves as a starting point for developing new plugins. It includes examples of configuration, Docker Compose templates, build materials, and hooks.

#### Features

- Example configuration schema
- Docker Compose templates
- Build materials
- Lifecycle hooks

#### Configuration

The Template Plugin supports both basic and advanced configuration options:

```yaml
# Basic configuration
database:
  host: localhost
  port: 5432
  name: myapp
  user: dbuser
  password: dbpassword

app:
  debug: false
  log_level: info
  secret_key: your-secret-key-here

server:
  host_port: 8080
```

Advanced configuration options:

```yaml
# Advanced configuration
email:
  smtp_server: smtp.example.com
  smtp_port: 587
  use_tls: true
  sender: noreply@example.com

features:
  enable_registration: true
  enable_social_login: false
  maintenance_mode: false
```

#### Environment Variables

The Template Plugin supports the following environment variables:

- `DB_HOST`: Database host
- `DB_PORT`: Database port
- `DB_NAME`: Database name
- `DB_USER`: Database username
- `DB_PASSWORD`: Database password
- `SECRET_KEY`: Application secret key
- `DEBUG`: Enable debug mode (true/false)
- `LOG_LEVEL`: Logging level (debug, info, warning, error, critical)
- `HOST_PORT`: Host port to bind

#### Deployment Examples

Basic deployment:

```bash
# Deploy with default configuration
platform plugin deploy template

# Deploy with custom configuration
platform plugin deploy template --config my-config.yaml
```

Production deployment:

```bash
# Deploy for production
platform plugin deploy template --env production --replicas 3
```

Development setup:

```bash
# Deploy for development with debugging
platform plugin deploy template --env development --debug
```

### Physical Host Template

The Physical Host Template is designed for deploying applications directly on physical machines or virtual machines without using Docker containers. It uses SSH to connect to the target machine and install the application, configure services, and set up the environment.

#### Features

- Supports both physical hosts and VMs
- Configurable installation directories
- Automatic setup of Python virtual environment
- Configuration of Supervisor for process management
- Nginx setup for web serving
- Database setup (PostgreSQL)
- Storage volume configuration
- Network interface configuration

#### Requirements

- SSH access to the target machine
- Python 3.x on the target machine
- Sudo privileges on the target machine

#### Configuration

The Physical Host Template is configured using a JSON schema. The main configuration sections are:

Host Configuration:

```json
"host": {
  "type": "physical",  // or "vm"
  "connection": {
    "host": "example.com",
    "port": 22,
    "user": "admin",
    "key_file": "/path/to/key.pem"  // or use password
  },
  "os": {
    "family": "debian",  // or "redhat", "suse", "arch"
    "version": "11"
  },
  "resources": {
    "cpu_threads": 4,
    "ram_mb": 8192
  }
}
```

Application Configuration:

```json
"app": {
  "debug": false,
  "log_level": "info",
  "secret_key": "your-secret-key",
  "allowed_hosts": ["example.com", "localhost"],
  "install_dir": "/opt/app",
  "data_dir": "/var/lib/app",
  "log_dir": "/var/log/app",
  "user": "app",
  "group": "app"
}
```

Database Configuration:

```json
"database": {
  "host": "localhost",
  "port": 5432,
  "name": "app",
  "user": "postgres",
  "password": "postgres",
  "max_connections": 100
}
```

Server Configuration:

```json
"server": {
  "host_port": 8080,
  "workers": 4,
  "timeout": 60
}
```

Storage Configuration:

```json
"storage": {
  "volumes": [
    {
      "name": "data",
      "path": "/var/lib/app/data",
      "size_gb": 10,
      "type": "local"
    },
    {
      "name": "nfs-data",
      "path": "/mnt/nfs-data",
      "size_gb": 100,
      "type": "nfs",
      "options": {
        "server": "nfs-server.example.com",
        "export": "/exports/data"
      }
    }
  ]
}
```

Network Configuration:

```json
"network": {
  "networks": [
    {
      "name": "app-network",
      "cidr": "192.168.1.0/24",
      "type": "physical",
      "interface": "eth0"
    }
  ]
}
```

#### Deployment Process

1. The pre-deployment script checks that the required tools are available.
2. The deployment script connects to the target machine via SSH.
3. It installs the required packages based on the OS family.
4. It creates the application user and group.
5. It creates the required directories.
6. It copies the application files to the target machine.
7. It sets up a Python virtual environment and installs dependencies.
8. It creates the application configuration.
9. It sets up Supervisor to manage the application process.
10. It sets up Nginx as a reverse proxy.
11. It configures the database (if local).
12. It configures storage volumes and network interfaces.
13. It restarts the services.
14. The post-deployment script verifies that the deployment was successful.

## Creating Custom Plugins

To create a custom plugin for Windflow, follow these steps:

1. **Create a new directory** for your plugin with the standard structure.
2. **Define your plugin metadata** in `plugin.yml`.
3. **Create configuration schema** in `config/schema.json`.
4. **Implement lifecycle hooks** in the `hooks/` directory.
5. **Add any necessary scripts** to the `scripts/` directory.
6. **Document your plugin** in `README.md`.

### Example: Creating a Simple Plugin

1. Create the plugin directory structure:

```bash
mkdir -p my-plugin/{config,hooks,scripts}
touch my-plugin/plugin.yml
touch my-plugin/README.md
```

2. Define the plugin metadata in `plugin.yml`:

```yaml
name: my-plugin
version: 1.0.0
description: My custom plugin for Windflow
author: Your Name
license: MIT

dependencies:
  - core: ">=1.0.0"

config:
  schema: config/schema.json
  defaults: config/defaults.yaml

hooks:
  pre-deploy: hooks/pre-deploy.sh
  post-deploy: hooks/post-deploy.sh
```

3. Create a configuration schema in `config/schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "app": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string",
          "description": "The name of the application"
        },
        "version": {
          "type": "string",
          "description": "The version of the application"
        }
      },
      "required": ["name"]
    }
  }
}
```

4. Create default configuration in `config/defaults.yaml`:

```yaml
app:
  name: my-app
  version: 1.0.0
```

5. Implement a pre-deploy hook in `hooks/pre-deploy.sh`:

```bash
#!/bin/bash
echo "Running pre-deploy hook for my-plugin"
# Add your pre-deployment logic here
exit 0
```

6. Implement a post-deploy hook in `hooks/post-deploy.sh`:

```bash
#!/bin/bash
echo "Running post-deploy hook for my-plugin"
# Add your post-deployment logic here
exit 0
```

7. Make the hook scripts executable:

```bash
chmod +x my-plugin/hooks/*.sh
```

8. Document your plugin in `README.md`:

```markdown
# My Plugin

A custom plugin for Windflow.

## Features

- Feature 1
- Feature 2

## Configuration

Example configuration:

```yaml
app:
  name: my-app
  version: 1.0.0
```

## Usage

```bash
platform plugin deploy my-plugin
```
```

## Plugin Best Practices

1. **Follow the standard structure**: Use the standard directory structure for your plugin.
2. **Document your plugin**: Provide comprehensive documentation in your README.md file.
3. **Validate configuration**: Use JSON Schema to validate user configuration.
4. **Provide sensible defaults**: Include default configuration values.
5. **Handle errors gracefully**: Ensure your hooks and scripts handle errors properly.
6. **Use environment variables**: Allow configuration via environment variables.
7. **Version your plugin**: Use semantic versioning for your plugin.
8. **Test thoroughly**: Test your plugin in different environments.
9. **Keep it focused**: Each plugin should have a clear, focused purpose.
10. **Provide examples**: Include usage examples in your documentation.
