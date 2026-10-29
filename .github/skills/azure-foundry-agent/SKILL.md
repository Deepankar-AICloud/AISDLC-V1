---
name: azure-foundry-agent
description: 'Invoke Azure AI Foundry agents for various tasks. Use when asked to "invoke foundry agent", "use azure agent", "call foundry agent", or when user specifies a specific agent name to use. Supports multiple configurable agents. Routes queries to the specified Azure Foundry agent and returns AI-generated responses.'
---

# Azure Foundry Agent Invoker

A skill for invoking Azure AI Foundry agents to answer questions and perform tasks. Supports multiple agents that can be configured in a YAML file.

## When to Use This Skill

- User asks to "invoke a foundry agent" or "use azure agent"
- User specifies a specific agent name to invoke
- User wants to interact with any configured Azure Foundry agent
- User asks what agents are available

## Prerequisites

- Azure CLI installed and authenticated (`az login`)
- Python 3.11+ installed
- Required packages installed:
  ```bash
  pip install --pre azure-ai-projects>=2.0.0b1 azure-identity pyyaml
  ```
- Access to Azure AI Foundry endpoint
- Proper Azure credentials configured (DefaultAzureCredential)

## Configuration

Agents are configured in the `references/agents-config.yaml` file:

```yaml
endpoint: "https://your-resource.services.ai.azure.com/api/projects/your-project"

agents:
  - name: "agent-name"
    description: "What the agent does"
    triggers:
      - "keyword1"
      - "keyword2"
```

### Adding a New Agent

1. Open `references/agents-config.yaml`
2. Add a new agent entry under the `agents:` section:
   ```yaml
   - name: "your-new-agent"
     description: "Description of what your agent does"
     triggers:
       - "trigger keyword 1"
       - "trigger keyword 2"
   ```
3. Save the file

## Step-by-Step Workflow

### Step 1: Identify the Agent

When the user requests to invoke a Foundry agent:
1. Check if they specified an agent name
2. If not, ask which agent they want to use or list available agents

### Step 2: List Available Agents (Optional)

To see all configured agents:

```bash
python .github/skills/azure-foundry-agent/scripts/invoke_agent.py --list
```

### Step 3: Execute the Agent

Run the Python script with the agent name and query:

```bash
python .github/skills/azure-foundry-agent/scripts/invoke_agent.py "<agent_name>" "<user_query>"
```

### Step 4: Handle Unknown Agents

If the user specifies an agent that's not in the configuration:
- The script will show an error message
- Display the list of available agents
- Instruct the user to either select from available agents OR add their agent to the config file

## Example Usage

**List available agents:**
```bash
python .github/skills/azure-foundry-agent/scripts/invoke_agent.py --list
```

**Invoke the work assistant:**
```bash
python .github/skills/azure-foundry-agent/scripts/invoke_agent.py "work-assitant" "What can you help me with?"
```

**Invoke with partial name match:**
```bash
python .github/skills/azure-foundry-agent/scripts/invoke_agent.py "work" "Tell me about the project"
```

## Available Agents

Currently configured agents (see `references/agents-config.yaml` for full list):

| Agent Name | Description |
|------------|-------------|
| `work-assitant` | Work Assistant for project documents and work items |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Agent not found in config | Add the agent to `references/agents-config.yaml` |
| Authentication failed | Run `az login` to authenticate with Azure |
| Agent not found in Azure | Verify the agent name matches exactly in Azure Foundry |
| Connection timeout | Check network connectivity and endpoint URL |
| Missing packages | Run `pip install --pre azure-ai-projects>=2.0.0b1 azure-identity pyyaml` |

## Error Messages

**"Agent 'X' not found in configuration"**
- The specified agent is not in the config file
- Either select from available agents or add your agent to `references/agents-config.yaml`

**"Authentication Error"**
- Run `az login` to authenticate with Azure

**"Agent Not Found" (from Azure)**
- The agent exists in config but not in Azure Foundry
- Verify the agent name in Azure AI Foundry portal

## References

- Config file: `.github/skills/azure-foundry-agent/references/agents-config.yaml`
- Azure AI Foundry documentation: https://learn.microsoft.com/azure/ai-services/
- Azure Identity documentation: https://learn.microsoft.com/python/api/azure-identity/
