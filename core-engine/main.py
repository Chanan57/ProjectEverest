import yaml
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

def load_config(config_path='../config.yaml'):
    """
    Loads the system configuration from a YAML file.
    """
    if not os.path.exists(config_path):
        print(f"Warning: Configuration file {config_path} not found.")
        return {}
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def main():
    print("Project Everest: Core Engine Starting...")
    
    # Load configuration
    config = load_config()
    
    # Example access
    risk_config = config.get('risk_management', {})
    max_risk = os.getenv('MAX_RISK_PCT', risk_config.get('max_risk_pct', 0.01))
    
    print(f"Operational Risk Limit: {max_risk}")
    
    # Initialize MetaTrader 5, Strategies, etc.
    # ...

if __name__ == "__main__":
    main()
