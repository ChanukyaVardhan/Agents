from langgraph.graph import StateGraph, END
from agents.data_agent import DataAgent
from agents.metadata_resolver_agent import MetadataAgent
from agents.analysis_agent import AnalysisAgent
from state import GlobalState


OUTPUT_TRACE_PATH = "output/output.txt"
data_agent = DataAgent(OUTPUT_TRACE_PATH)
metadata_agent = MetadataAgent(OUTPUT_TRACE_PATH)
analysis_agent = AnalysisAgent(OUTPUT_TRACE_PATH)


def data_node(state: GlobalState) -> GlobalState:
    result = data_agent.execute(state)
    return result

def metadata_node(state: GlobalState) -> GlobalState:
    result = metadata_agent.execute(state)
    return result

def analysis_node(state: GlobalState) -> GlobalState:
    result = analysis_agent.execute(state)
    return result


# Condition for looping
def data_check(state: GlobalState) -> str:
    # return END if state.required_data_loaded else "data_agent"
    return "metadata_agent" if state.required_data_loaded else "data_agent"

def answer_check(state: GlobalState) -> str:
    return END if state.final_answer else "analysis_agent"

builder = StateGraph(GlobalState)

builder.add_node("data_agent", data_node)
builder.add_node("metadata_agent", metadata_node)
builder.add_node("analysis_agent", analysis_node)

builder.set_entry_point("data_agent")
builder.add_conditional_edges("data_agent", data_check)
builder.add_edge("metadata_agent", "analysis_agent")
builder.add_conditional_edges("analysis_agent", answer_check)

graph = builder.compile()


if __name__ == "__main__":
    user_query = "Based on Jalen Brunson's performance in the recent games, give me 3 player market bets each that are at max -200 bet odds (i.e., -250, -300) and are very probably to hit in the next game."

    initial_state = GlobalState(user_query=user_query)
    final_state = graph.invoke(initial_state)
