"""
Stockelper Streamlit Frontend Application
주식 투자 도우미 챗봇의 웹 인터페이스
"""

import streamlit as st
import requests
from uuid import uuid4
from typing import Dict, Any

# 설정
LLM_SERVER_URL = os.getenv("LLM_SERVER_URL", "http://localhost:8000")

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
    
    def call_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """API 호출"""
        try:
            response = requests.post(f"{LLM_SERVER_URL}/stock/chat", json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"API 호출 중 오류가 발생했습니다: {e}")
            return {"message": "죄송합니다. 서버에 연결할 수 없습니다.", "trading_action": {}}
    
    def display_messages(self):
        """채팅 메시지 표시"""
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"], unsafe_allow_html=True)
    
    def handle_user_input(self, query: str):
        """사용자 입력 처리"""
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
            with st.spinner("Thinking..."):
                data = self.call_api(payload)
                bot_msg = data.get("message", "")
                trading_action = data.get("trading_action", {})
                
                # 일반 답변 저장·표시
                st.session_state.messages.append({"role": "assistant", "content": bot_msg})
                st.markdown(bot_msg, unsafe_allow_html=True)
                
                # trading_action이 있으면 확인 대화 트리거
                if trading_action:
                    st.session_state.pending_trading_action = trading_action
    
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
        feedback_payload = {
            "user_id": 1,
            "thread_id": st.session_state.session_id,
            "message": st.session_state.messages[-1]["content"],
            "human_feedback": feedback
        }
        
        with st.spinner("Processing feedback..."):
            data = self.call_api(feedback_payload)
            fb_msg = data.get("message", "")
            
            st.session_state.messages.append({"role": "assistant", "content": fb_msg})
            st.markdown(fb_msg, unsafe_allow_html=True)
        
        # 확인 완료 후 상태 정리
        del st.session_state["pending_trading_action"]
        st.rerun()
    
    def run(self):
        """애플리케이션 실행"""
        # 채팅 메시지 표시
        self.display_messages()
        
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