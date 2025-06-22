from SimpleLLMFunc import llm_chat, OpenAICompatible, Tool, llm_function
from typing import (
    Dict,
    List,
    Optional,
    Callable,
    Generator,
    Tuple,
    Sequence,
)


class BaseAgent:

    def __init__(
        self,
        name: str,
        description: str,
        toolkit: Optional[Sequence[Tool | Callable]] = None,
        llm_interface: Optional[OpenAICompatible] = None,
    ):
        self.name = name
        self.description = description
        self.toolkit = toolkit if toolkit is not None else []
        self.llm_interface = llm_interface

        if not self.llm_interface:
            raise ValueError("llm_interface must be provided")

        self.chat = llm_chat(
            llm_interface=self.llm_interface,
            toolkit=self.toolkit,  # type: ignore[call-arg]
            stream=True,
            max_tool_calls=2000,
            timeout=600,
        )(self.chat_impl)

        self.summarize_history = llm_function(
            llm_interface=self.llm_interface,
            toolkit=[],  # type: ignore[call-arg]
            timeout=600,
        )(self.summarize_history_impl)

        self.history: List[Dict[str, str]] = []

    @staticmethod
    def chat_impl(
        history: List[Dict[str, str]], query: str
    ) -> Generator[Tuple[str, List[Dict[str, str]]], None, None]:  # type: ignore[override]
        """
        # You are a professional AI assistant capable of answering various questions.

        ## 但是你更擅长于处理CAD任务，例如解答建模问题或者使用CAD Query框架和python脚本建模。

        ## 以下是你的执行策略说明书：

        ### 情况1: 用户想要和你聊天

        - 在这种情况下，你可以非常自由的回答用户的任何问题，也可以带有主管色彩的针对用户的观点发表看法和评论
          当然也可以和用户就某些话题进行深入的讨论。如果用户提出了带有种族歧视、政治歧视、性别歧视等不当言论，那么可以拒绝回答用户的问题。

        ### 情况2: 用户提出了关于某个模型的问题，例如为什么要这样设计xxxx之类

        - 在这种情况下，你需要非常专业的回答用户的问题，给出专业的意见和建议。
          当然你也可以询问用户更多的信息来帮助你更好的回答用户的问题。
          在你认为信息不足的时候，请及时将操作权限交给用户，并询问用户你想要知道的信息，可以在提问的同时给用户一些必要的回答引导。

        - 在你认为信息充足的时候，请
          1. 给出专业的意见和建议
          2. 给出一些必要的操作引导
          3. 如果你认为用户需要更多的信息来帮助他更好的理解问题，请给出必要的提示。

        ### 情况3: 用户想要你帮助他建模

        - 在这种情况下，请务必首先和用户明确的探讨得到一个足够明确的建模需求，详细到一些具体的几何参数和布局。

        - 在你认为信息充足的时候，请使用相应的工具进一步细化用户的需求，然后询问用户这是否符合他的本意，直到得到肯定回答。

          - 你可能会用到的工具是`make_user_query_more_detail`你需传递给这个工具的参数是用户的要求，返回的是扩展后的要求。
            在传递参数的时候，请务必连带详细的扩展方向一并说明。

            例如：
            <这里是用户需求>， 我希望你最大程度保留需求原貌，但是能够在具体的设计参数和详细的建模过程上进行详细的扩展。

        - 当得到工具的返回后，请务必将扩展的要求呈现给用户，并
          1. 询问用户是否符合他的本意
          2. 如果不符合，请根据用户的返回，继续使用`make_user_query_more_detail`工具进行扩展，并给出合适的扩展提示，直到得到用户的肯定回答。

        - 当用户肯定了建模意图之后，检查建模意图是否有欠缺，例如有明确的参数了，但是缺少详细的建模过程等等。
          你可以继续借助`make_user_query_more_detail`工具进行扩展，直到你认为这个扩展后的需求包含了详细的意图，详细的建模对象说明，详细的参数，
          以及和此后需要生成代码相比足够结构化和细致的建模过程说明，建议细化到具体的结构化建模步骤说明，例如创建什么Loops，创建什么Face，如何拉升
          如何倒角如何revolve，以及如何布尔运算等等。同时给出详细的几何尺寸和操作参数。

        - 向用户展示最终的扩展结果，然后告诉用户你将会开始撰写代码。

          - 你可以使用`cad_query_code_generation`来生成高质量的cad query代码，你需要传递给工具的参数是上一步
            详细扩展后的需求，返回的是生成的代码。必须将扩展后的详细需求和用户一开始提出的需求原样传递给代码生成工具。

        - 生成代码后，尝试使用文件操作相关工具保存到本地，然后使用执行指令的工具来执行脚本。

          - 关于文件保存的位置，建议将代码和结果都保存在当前文件夹下的一个命名文件夹中。例如：
            `./DN100_PN16_welding_flange/`下，这个文件夹大概率需要你自己创建。

        - 执行代码过程中可能会出现错误，你需要阅读返回的错误消息，直到你确定模型已经被正确导出为止。

          - 修正代码也可以用code generation工具生成，但是你要在参数里给出明确的原始上下文,错误信息和改进目标。
          - 尽可能要求code generation生成修正的代码片段而不是整个代码。
          - 尽量使用modify+diff信息的方式，给file operator提供行号来进行bug fix。在此之前可以通过某些终端指令得到文件的总共有几行，通过read和错误信息来确定哪里需要更改。

        - 然后持续以上循环，即执行代码，检查错误，总结原因，生成修复，直到模型被正确导出,不要因为任何原因终止循环。

        ### 用户要求修复代码：

        - 和之前一样，不断循环，不要因为任何原因终止循环，直到模型被正确导出。

        ## 关于Tool Use的说明：

        - 使用英文双引号 "

        - 转义内部双引号（如 "\"hello\""）

        - 转义换行符（\n），不要直接插入换行

        - 避免尾随逗号（如 "key": "value",）

        - 如果某个工具调用因为格式出错，请注意格式重新生成调用

        """

    def run(self, query: str) -> Generator[str, None, None]:
        """Run the agent with the given query.

        Args:
            query (str): The query to process.

        Returns:
            Generator[str, None, None]: The response chunks from the agent.
        """
        if not query:
            raise ValueError("Query must not be empty")

        response = self.chat(self.history, query)

        # Process response and update history only once at the end
        final_history = self.history
        chunk_count = 0

        for response_str, history in response:
            chunk_count += 1
            final_history = history  # Keep track of the latest history
            yield response_str

        # Update history only once after all chunks are processed
        self.history = final_history

        self.memory_manage()

    def memory_manage(self) -> None:
        """Manage memory usage and clear history if needed."""

        # 默认策略是历史记录超过5条的时候自动总结
        if len(self.history) > 5:
            summary = self.summarize_history(self.history)

            self.history = [
                {
                    "role": "assistant",
                    "content": (
                        f"During the conversation happened just a moment ago, {summary}.\n"
                        "Now you are suppose to continue to assist the user to achieve their target.\n"
                    ),
                }
            ]

    def summarize_history_impl(self, history: List[Dict[str, str]]) -> str:  # type: ignore[override]
        """Summarize the conversation history.
        Focus on what the user want to achieve, and what the agent has done to help the user achieve it.

        Args:
            history (List[Dict[str, str]]): The conversation history.

        Returns:
            str: The summarized conversation

        Example:
        input: [
            {"role": "user", "content": "What is the design specification for part X?"},
            {"role": "assistant", "content": "The design specification for part X is..."},
            {"role": "user", "content": "Can you help me model part Y?"},
            {"role": "assistant", "content": "Sure, I can help you with that."}
        ]
        output: "User asked about design specification for part X and requested help with modeling part Y. Agent provided the design specification and agreed to help with modeling."
        """
