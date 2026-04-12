import random
import textwrap

"""
Everest v8.0 — Trading Psychology Module
========================================
Inspired by Mark Douglas ("Trading in the Zone").
Provides psychological conditioning to the human trader
to prevent manual intervention and emotional mistakes.
"""

MARK_DOUGLAS_QUOTES = [
    # --- FUNDAMENTAL TRUTHS OF SYSTEM TRADING ---
    "Anything can happen. Do not try to predict the market. Let the algorithm calculate the probabilities.",
    "You don't need to know what is going to happen next in order to make money. The machine just needs to execute the edge.",
    "There is a random distribution between wins and losses for any given set of variables that define an edge.",
    "An edge is nothing more than an indication of a higher probability of one thing happening over another.",
    "Every moment in the market is unique. Do not link the bot's current trade to its last trade.",
    
    # --- ACCEPTING THE MACHINE ---
    "When you genuinely accept the risks of the algorithmic strategy, you will be at peace with any outcome.",
    "If you want to create consistency, you have to completely surrender the execution process to the system.",
    "The market does not owe you anything. It just provides opportunities that the algorithm captures.",
    "A loss is simply the statistical cost of finding out if the edge was going to work this time. It is a business expense.",

    # --- THE PROBABILISTIC MINDSET ---
    "To think in probabilities, you have to create a mental framework that accepts the law of large numbers. Let the bot reach those numbers.",
    "When you truly believe that probabilities play out over a large sample size, you will no longer care if any individual trade is a winner or a loser.",
    "The market generates behavior patterns. The machine identifies those patterns. You just watch.",
    "Why do unsuccessful traders intervene? They crave certainty. Trust the math instead.",

    # --- EMOTIONAL DETACHMENT ---
    "If you can learn to create a state of mind that is not affected by the market's temporary behavior, the struggle will cease.",
    "The best system managers believe, without a shred of doubt, that they can't know for sure what's going to happen next.",
    "Euphoria is just as dangerous as fear. Do not let the feeling of the bot's winning streak convince you to intervene or blindly increase risk.",

    # --- THE GOLDEN RULES OF HANDS-OFF TRADING ---
    "Your system has a verified edge. Your only job is to leave the machine alone. Let the bot work.",
    "Let go of the need to be right. Everest is playing probabilities, not certainties.",
    "Intervening in the system means you have stopped trusting the verified mathematical edge and started trusting your own fear.",
    "Fear of missing out (FOMO) is a symptom of believing you know what will happen next. You don't.",
    "The goal isn't to make money on this specific trade. The goal is flawless, emotionless execution over a series of 100 trades.",
    "Any time you feel the urge to manually close the bot's trade, ask yourself: Am I acting on the edge, or am I acting out of fear?"
]

def get_conditioning_quote():
    """Returns a random Mark Douglas trading psychology quote."""
    return random.choice(MARK_DOUGLAS_QUOTES)

def print_psychology_block():
    """Returns a formatted block for the terminal dashboard."""
    quote = get_conditioning_quote()
    
    # Word wrap the quote so it doesn't break terminal width
    wrapped_quote = textwrap.fill(f'"{quote}"', width=62, initial_indent='    ', subsequent_indent='    ')
    
    block =  f"{'-'*70}\n"
    block += f" 🧘 TRADING IN THE ZONE (MARK DOUGLAS):\n"
    block += f"{wrapped_quote}\n"
    block += f"{'-'*70}\n"
    
    return block

# Example usage for testing the dashboard output:
if __name__ == "__main__":
    print(print_psychology_block())
