# Multi-source inventory reconciliation agent

A small, deterministic Python agent that reconciles one SKU across three independent local HTTP APIs:

warehouse management system (WMS)

e-commerce platform

supplier API

It detects discrepancies, decides which source is authoritative using explicit rules, changes what it queries next based on earlier results, and writes a structured JSONL audit trail explaining every decision.

The implementation uses only Python's standard library. No API keys, accounts, packages, cloud services, databases, or internet access are required.

# Why this meets the assignment

The default demo (SKU-RED-CHAIR) does this:

```text
warehouse -> reports 7 available
           |
           +-- 7 <= low-stock threshold (10)
               so the agent chooses SUPPLIER next

supplier  -> reports 40 available
           |
           +-- 40 != 7
               so the agent detects a discrepancy
               and chooses E-COMMERCE next

ecommerce -> reports 9 available
           |
           +-- three sources now checked
               apply authority rules

final     -> trust warehouse = 7
```

That is not a fixed warehouse -> ecommerce -> supplier script. A second fixture (SKU-BLUE-LAMP) produces a different order:

warehouse -> ecommerce -> supplier

A third fixture (SKU-GREEN-MUG) makes warehouse deliberately stale, so e-commerce becomes authoritative.

# Repository layout

```text
inventory-reconciliation-agent/
├── README.md
├── run_demo.py
├── inventory_agent/
│   ├── __init__.py
│   ├── agent.py
│   ├── audit.py
│   ├── mock_sources.py
│   └── models.py
└── tests/
    └── test_agent.py
```

# What each file does

run_demo.py — one-command entry point for the video/demo.

inventory_agent/mock_sources.py — starts three separate localhost HTTP API servers on three separate ports. Each API has a different response schema.

inventory_agent/agent.py — HTTP calls, schema normalization, adaptive next-step planning, discrepancy detection, freshness checks, and authority selection.

inventory_agent/audit.py — writes one JSON object per decision step to logs/reconciliation.jsonl.

inventory_agent/models.py — simple dataclasses for normalized observations and the final result.

inventory_agent/__init__.py — makes the main classes easy to import.

tests/test_agent.py — end-to-end tests that prove the discrepancy case, adaptive query order, and stale-source rule.

# Authority rules

The rules are deliberately explicit and deterministic.

# Rule 1 — health and freshness first

A source is eligible only if:

its health flag says it is healthy/reachable; and

its observation is no more than 300 seconds old.

If a source is stale or unhealthy, it cannot win.

# Rule 2 — domain priority for our own sellable stock

Among eligible sources:

warehouse > ecommerce > supplier

Why:

Warehouse knows physical on_hand - reserved, so it is the strongest source for what we actually own now.

E-commerce is customer-facing and useful, but it can lag warehouse movements.

Supplier tells us what the supplier can ship, not what is physically in our warehouse, so it is advisory for our own stock count.

# Rule 3 — discrepancy definition

After normalization, any difference greater than 0 units is a discrepancy.

The threshold is intentionally strict for a small demo. A production system would normally configure this by SKU/category.

# Adaptive planning rules

After the warehouse response:

if warehouse is stale/unhealthy -> query e-commerce next;

else if warehouse available quantity is <= 10 -> query supplier next;

else -> query e-commerce next.

After two sources:

if quantities disagree -> query the remaining third source;

if quantities agree -> stop early because another request is unnecessary.

That means the agent decides what to check next from what it just learned.

# Run it — simplest possible instructions

# 1. Check Python

Use Python 3.11 or newer.

python --version

If your machine uses python3 instead of python, use python3 in every command below.

# 2. Open a terminal in this repository folder

You should be in the folder containing run_demo.py.

Example check:

python -c "from pathlib import Path; print(Path('run_demo.py').exists())"

It should print:

True

# 3. Run the end-to-end demo

python run_demo.py

No installation step is required.

What happens:

Python starts three separate HTTP servers on unused localhost ports.

The agent plans to query warehouse first.

Warehouse returns 7 available for SKU-RED-CHAIR.

Because 7 <= 10, the agent chooses supplier next.

Supplier returns 40, so the agent detects a discrepancy.

The discrepancy causes it to query e-commerce.

E-commerce returns 9.

The authority policy checks health, freshness, and source priority.

Fresh/healthy warehouse wins with quantity 7.

Every plan, request, observation, and decision is printed as JSON.

The same records are written to logs/reconciliation.jsonl.

The three local servers shut down automatically.

Expected key result:

query_order = ["warehouse", "supplier", "ecommerce"]
discrepancy_detected = true
authoritative_source = "warehouse"
authoritative_quantity = 7

The exact temporary localhost port numbers and elapsed milliseconds will vary.

# 4. Read the audit log

Open:

logs/reconciliation.jsonl

Each line contains:

step — exact order of events;

event — plan/request/observation/final decision;

action — what the agent did;

reason_code — short machine-friendly rule name;

rationale — plain-English explanation;

evidence — the data used for that decision.

This is the main evidence that a reviewer can audit why the agent made each choice.

# 5. Run the tests

python -m unittest discover -s tests -v

You should see three tests ending in:

OK

The tests prove:

the default discrepancy is detected;

low stock causes supplier to be queried second;

high stock changes the second query to e-commerce;

stale warehouse data can lose authority to e-commerce.

# Easier Method to Run the Program

*Use this method if the instructions above are not compatible with your device or setup.*

If you're completely new to GitHub, Python, or using a terminal, don't worry — follow each step below in order.

# 1). Download the ZIP file from GitHub

On the GitHub project page, click the option to **download the project as a ZIP file**.

Once downloaded, the ZIP file should normally appear in your **Downloads** folder.

# 2). Extract the ZIP file

Open **File Explorer** and go to your **Downloads** folder.

Find the ZIP file you just downloaded, click it, and then select **Extract All**.

# 3). Choose where to extract the project

Once you click **Extract All**, you can name the folder whatever you want, although using the **project name** is recommended so that it is easier to recognise later.

After choosing the folder name/location, click **Extract** again.

# 4). Open Command Prompt or Terminal

Open **Command Prompt** or **Terminal** on your device, whether you're using a laptop or PC.

> **Beginner tip:** On Windows, you can press the **Windows key**, type **Command Prompt**, and press **Enter**.

# 5). Navigate to the project folder

In the command terminal, first type **exactly**:

```text
cd /d "%USERPROFILE%\Downloads\Multi-Source-Inventory-Reconcilliation-Agent-main\Multi-Source-Inventory-Reconcilliation-Agent-main"
```

Then press **Enter**.

> **Important:** The command above is based on where **I saved the project on my device**. If you saved or renamed the folder differently, replace the folder name/path with whatever you used.

# 6). Run the program

Once you are inside the correct project folder, type **exactly**:

```text
python run_demo.py
```

Finally, press **Enter**.

The project should now be running.

# 7). Don't forget the tests 

If you want to compile the tests, type **exactly"":

```text
python -m unittest discover -s tests -v
```
Finally, press Enter.

The tests should run


# Optional runs that prove it is adaptive

High-stock path:

python run_demo.py SKU-BLUE-LAMP

Expected order:

warehouse -> ecommerce -> supplier

Stale-warehouse path:

python run_demo.py SKU-GREEN-MUG

Expected authority:

ecommerce
