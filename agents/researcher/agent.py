from google.adk.agents import Agent
from google.adk.tools.google_search_tool import google_search
import json
import datetime
import os
import sqlite3

def log_to_db(agent_name, input_data, output_data, model="gemini-1.5-flash"):
    try:
        conn = sqlite3.connect('/home/iicc2/prai-roadshow-lab-1-starter/agent_storage.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO agent_logs (agent_name, input_text, output_text, model_used)
            VALUES (?, ?, ?, ?)
        ''', (agent_name, str(input_data), str(output_data), model))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database logging failed: {e}")

def save_output(agent_name, content):
    storage_dir = "/home/iicc2/prai-roadshow-lab-1-starter/outputs"
    os.makedirs(storage_dir, exist_ok=True)
    
    filename = f"{storage_dir}/{agent_name}_results.jsonl"
    data = {
        "timestamp": datetime.datetime.now().isoformat(),
        "content": content
    }
    
    with open(filename, "a") as f:
        f.write(json.dumps(data) + "\n")

MODEL = "gemini-2.5-pro"

# TODO: Define the Researcher Agent
# The researcher should be an Agent that uses the google_search tool
# and follows the instructions to gather information.
# ... existing imports ...

# Define the Researcher Agent
researcher = Agent(
    name="researcher",
    model=MODEL,
    description="Gathers information on a topic using Google Search.",
    instruction="""
    You are an expert researcher. Your goal is to find comprehensive and accurate information on the user's topic.
    Use the `google_search` tool to find relevant information.
    Summarize your findings clearly.
    If you receive feedback that your research is insufficient, use the feedback to refine your next search.
    """,
    tools=[google_search],
)

root_agent = researcher
