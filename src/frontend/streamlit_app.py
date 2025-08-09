"""
Stockelper Streamlit Frontend Application
주식 투자 도우미 챗봇의 웹 인터페이스
"""

import streamlit as st
import httpx
import json
import time
from uuid import uuid4
from typing import Dict, Any

# 설정
LLM_SERVER_URL = "http://localhost:21009"

class StockChatApp:
    """Stockelper 채팅 애플리케이션 클래스"""
    
    def __init__(self):
        self.setup_page()
        self.initialize_session_state()
    
    def setup_page(self):
        """페이지 설정"""
        st.set_page_config(
            page_title="Stockelper",
            page_icon="📈",
            layout="wide"
        )
        
        # 사이드바
        st.sidebar.title("📈 Stockelper")
        st.sidebar.button("Clear Chat History", on_click=self.clear_chat_history)
        
        # 메인 페이지
        st.title("Stockelper에 오신 것을 환영합니다!")
        st.subheader("원하는 주식에 대해 말씀해주세요.")
        st.write("주식 관련 정보를 활용하여 주식 투자에 도움을 드립니다.")
    
    def initialize_session_state(self):
        """세션 상태 초기화"""
        if "session_id" not in st.session_state:
            st.session_state.session_id = str(uuid4())
        
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": "저는 주식 투자 도우미 챗봇 Stockelper입니다. 원하는 종목과 관련된 질문을 해주세요.",
                }
            ]
    
    def clear_chat_history(self):
        """채팅 기록 초기화"""
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "저는 주식 투자 도우미 챗봇 Stockelper입니다. 원하는 종목과 관련된 질문을 해주세요.",
            }
        ]
        st.session_state.session_id = str(uuid4())
        
        # pending_trading_action 초기화
        if "pending_trading_action" in st.session_state:
            del st.session_state["pending_trading_action"]
    
    async def call_streaming_api(self, payload: Dict[str, Any]):
        """스트리밍 API 호출 (SSE 방식)"""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
                async with client.stream(
                    "POST", 
                    f"{LLM_SERVER_URL}/stock/chat", 
                    json=payload,
                    headers={"Accept": "text/event-stream"}
                ) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_content = line[6:]  # "data: " 제거
                            if data_content == "[DONE]":
                                yield "done", None, None
                                break
                            try:
                                json_data = json.loads(data_content)
                                if json_data.get("type") == "final":
                                    # final 메시지
                                    yield "final", json_data.get("message"), json_data
                                elif json_data.get("type") == "progress" or (json_data.get("step") and json_data.get("status")):
                                    # progress 메시지
                                    yield "progress", json_data.get("step"), json_data.get("status")
                            except json.JSONDecodeError:
                                continue
                                
        except Exception as e:
            yield "error", f"API 호출 중 오류가 발생했습니다: {e}", ""
    
    def display_messages(self):
        """채팅 메시지 표시"""
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"], unsafe_allow_html=True)
    
    async def handle_user_input_streaming(self, query: str):
        """사용자 입력 처리 (SSE 스트리밍)"""
        # 사용자 메시지 저장 및 표시
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.write(query)
        
        # API 호출
        payload = {
            "user_id": 1,
            "thread_id": st.session_state.session_id,
            "message": query
        }
        
        with st.chat_message("assistant"):
            status_placeholder = st.empty()
            message_placeholder = st.empty()
            
            # 스피너와 함께 진행 상황 표시
            with st.spinner("분석 중..."):
                running_tasks = {}  # 진행중인 작업들 추적
                
                def get_step_icon(step):
                    """step에 따른 아이콘 반환"""
                    if "Agent" in step:
                        return "🤖"
                    elif any(tool in step for tool in ["search", "analysis", "predict", "analize"]):
                        return "🔧"
                    elif step == "supervisor":
                        return "👨‍💼"
                    else:
                        return "⚙️"
                
                def update_status_display():
                    """현재 진행중인 모든 작업 표시"""
                    if running_tasks:
                        status_lines = []
                        for step, info in running_tasks.items():
                            step_icon = info["icon"]
                            status_text = f"{step_icon} **{step}** 🔄 *진행중*"
                            status_lines.append(status_text)
                        
                        combined_status = "\n\n".join(status_lines)
                        status_placeholder.markdown(combined_status)
                    else:
                        status_placeholder.empty()
                
                async for response_type, content, extra in self.call_streaming_api(payload):
                    if response_type == "progress":
                        step = content
                        status = extra
                        step_icon = get_step_icon(step)
                        
                        if status == "start":
                            # 진행중 목록에 추가
                            running_tasks[step] = {
                                "icon": step_icon,
                                "status": "진행중"
                            }
                        elif status == "end":
                            # 진행중 목록에서 제거
                            if step in running_tasks:
                                del running_tasks[step]
                        
                        # 현재 진행중인 모든 작업 표시
                        update_status_display()
                        
                    elif response_type == "final":
                        # 최종 결과 표시
                        final_message = content
                        final_data = extra
                        
                        # 모든 진행중 작업 완료 표시
                        if running_tasks:
                            completed_lines = []
                            for step, info in running_tasks.items():
                                step_icon = info["icon"]
                                completed_text = f"{step_icon} **{step}** ✅ *완료*"
                                completed_lines.append(completed_text)
                            
                            final_status = "\n\n".join(completed_lines)
                            status_placeholder.markdown(final_status)
                            time.sleep(1)  # 잠시 완료 상태 표시
                        
                        # 상태 표시 제거
                        status_placeholder.empty()
                        
                        # 최종 메시지 표시
                        message_placeholder.markdown(final_message, unsafe_allow_html=True)
                        
                        # 세션에 저장
                        st.session_state.messages.append({"role": "assistant", "content": final_message})
                        
                        # trading_action이 있다면 저장
                        if final_data.get("trading_action"):
                            st.session_state.pending_trading_action = final_data["trading_action"]
                        
                        break
                        
                    elif response_type == "error":
                        status_placeholder.empty()
                        st.error(f"오류: {content}")
                        break
                        
                    elif response_type == "done":
                        break
                
                # 최종 완료 후 상태 정리
                status_placeholder.empty()
    
    def handle_user_input(self, query: str):
        """사용자 입력 처리 (동기 버전)"""
        import asyncio
        
        # 비동기 함수 실행
        asyncio.run(self.handle_user_input_streaming(query))
    
    def handle_trading_confirmation(self):
        """거래 확인 처리"""
        if not st.session_state.get("pending_trading_action"):
            return
        
        action = st.session_state.pending_trading_action
        
        with st.chat_message("assistant"):
            st.write("💡 거래 제안이 들어왔습니다:")
            
            # 거래 정보를 더 보기 좋게 표시
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**종목코드**: {action.get('stock_code', 'N/A')}")
                st.write(f"**거래유형**: {action.get('order_side', 'N/A')}")
            with col2:
                st.write(f"**주문타입**: {action.get('order_type', 'N/A')}")
                st.write(f"**수량**: {action.get('order_quantity', 'N/A')}")
            
            if action.get('order_price'):
                st.write(f"**가격**: {action.get('order_price', 'N/A'):,}원")
            
            # 확인 버튼
            ok_col, cancel_col = st.columns(2)
            
            with ok_col:
                if st.button("✅ 예", key="confirm_yes"):
                    self.process_feedback(True)
            
            with cancel_col:
                if st.button("❌ 아니오", key="confirm_no"):
                    self.process_feedback(False)
    
    def process_feedback(self, feedback: bool):
        """피드백 처리"""
        # 피드백 결과를 세션 상태에 저장
        st.session_state.feedback_processing = {
            "feedback": feedback,
            "status": "processing"
        }
        
        # 확인 완료 후 상태 정리
        del st.session_state["pending_trading_action"]
        st.rerun()
    
    async def handle_feedback_processing_async(self, feedback: bool):
        """피드백 처리 (비동기)"""
        feedback_payload = {
            "user_id": 1,
            "thread_id": st.session_state.session_id,
            "message": st.session_state.messages[-1]["content"],
            "human_feedback": feedback
        }
        
        with st.chat_message("assistant"):
            status_placeholder = st.empty()
            message_placeholder = st.empty()
            
            with st.spinner("거래 처리 중..."):
                running_tasks = {}  # 피드백 처리 중 진행중인 작업들 추적
                
                def get_step_icon(step):
                    """step에 따른 아이콘 반환"""
                    if "Agent" in step:
                        return "🤖"
                    elif any(tool in step for tool in ["search", "analysis", "predict", "analize"]):
                        return "🔧"
                    elif step == "supervisor":
                        return "👨‍💼"
                    else:
                        return "💼"
                
                def update_status_display():
                    """현재 진행중인 모든 작업 표시"""
                    if running_tasks:
                        status_lines = []
                        for step, info in running_tasks.items():
                            step_icon = info["icon"]
                            status_text = f"{step_icon} **{step}** 🔄 *처리중*"
                            status_lines.append(status_text)
                        
                        combined_status = "\n\n".join(status_lines)
                        status_placeholder.markdown(combined_status)
                    else:
                        status_placeholder.empty()
                
                async for response_type, content, extra in self.call_streaming_api(feedback_payload):
                    if response_type == "progress":
                        step = content
                        status = extra
                        step_icon = get_step_icon(step)
                        
                        if status == "start":
                            # 진행중 목록에 추가
                            running_tasks[step] = {
                                "icon": step_icon,
                                "status": "처리중"
                            }
                        elif status == "end":
                            # 진행중 목록에서 제거
                            if step in running_tasks:
                                del running_tasks[step]
                        
                        # 현재 진행중인 모든 작업 표시
                        update_status_display()
                        
                    elif response_type == "final":
                        final_message = content
                        status_placeholder.empty()
                        message_placeholder.markdown(final_message, unsafe_allow_html=True)
                        st.session_state.messages.append({"role": "assistant", "content": final_message})
                        break
                        
                    elif response_type == "error":
                        status_placeholder.empty()
                        st.error(f"오류: {content}")
                        break

    def handle_feedback_processing(self, feedback: bool):
        """피드백 처리 (동기 버전)"""
        import asyncio
        asyncio.run(self.handle_feedback_processing_async(feedback))
    
    def run(self):
        """애플리케이션 실행"""
        # 채팅 메시지 표시
        self.display_messages()
        
        # 피드백 처리 확인
        if st.session_state.get("feedback_processing"):
            feedback_info = st.session_state.feedback_processing
            if feedback_info["status"] == "processing":
                self.handle_feedback_processing(feedback_info["feedback"])
                del st.session_state["feedback_processing"]
                st.rerun()
        
        # 사용자 입력 처리
        if query := st.chat_input("Say something"):
            self.handle_user_input(query)
            st.rerun()
        
        # 거래 확인 처리
        self.handle_trading_confirmation()

def main():
    """메인 함수"""
    app = StockChatApp()
    app.run()

if __name__ == "__main__":
    main()