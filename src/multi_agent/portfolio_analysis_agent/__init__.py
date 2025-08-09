from .agent import PortfolioAnalysisAgent
from .prompt import SYSTEM_TEMPLATE
from .tools import *

agent = PortfolioAnalysisAgent(
    model="gpt-4o-mini",
    tools=[
        PortfolioAnalysisTool(),
    ],
    system=SYSTEM_TEMPLATE,
    name="PortfolioAnalysisAgent",
)