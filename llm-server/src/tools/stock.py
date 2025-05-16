from typing import Type, Optional
from langchain_core.tools import BaseTool
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
import dotenv
import os
import requests
import aiohttp
import json
import logging
import time
import asyncio

logger = logging.getLogger(__name__)

from prophet import Prophet
import pandas as pd
import FinanceDataReader as fdr
from statsmodels.tsa.arima.model import ARIMA
import numpy as np

dotenv.load_dotenv(override=True)

URL_BASE = "https://openapi.koreainvestment.com:9443"


# KIS Auth
class AnalysisStockInput(BaseModel):
    stock_code: str = Field(
        description="The stock code of the company you want to analyze."
    )


class AnalysisStockTool(BaseTool):
    name: str = "analysis_stock"
    description: str = (
        "A comprehensive stock analysis tool that provides key market information, price trends, trading status, investment indicators (PER, PBR, EPS, BPS), foreign ownership ratio, and market warning signals for listed companies."
    )
    args_schema: Type[BaseModel] = AnalysisStockInput

    async def auth(self):
        try:
            auth_url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
            auth_body = {
                "grant_type": "client_credentials",
                "appkey": os.getenv("KIS_APP_KEY"),
                "appsecret": os.getenv("KIS_APP_SECRET"),
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(auth_url, json=auth_body) as response:
                    status_code = response.status
                    text = await response.text()

                    logger.info(f"Auth request URL: {auth_url}")
                    logger.info(f"Auth request body: {auth_body}")
                    logger.info(f"Auth response status: {status_code}")
                    logger.info(f"Auth response body: {text}")

                    if status_code == 200:
                        response_data = json.loads(text)
                        if "access_token" in response_data:
                            os.environ["KIS_ACCESS_TOKEN"] = response_data[
                                "access_token"
                            ]
                            # print("access_token: ", response_data["access_token"])
                            return True
                        else:
                            logger.error("No access token in response")
                            return False
                    elif status_code == 403:
                        # 토큰 발급 제한 (1분당 1회) 에러인 경우 60초 대기
                        response_json = json.loads(text)
                        if (
                            "error_code" in response_json
                            and response_json["error_code"] == "EGW00133"
                        ):
                            logger.info(
                                "Token rate limit exceeded. Waiting 60 seconds..."
                            )
                            await asyncio.sleep(60)
                            return await self.auth()
                        else:
                            logger.error(
                                f"Auth failed with status code {status_code}: {text}"
                            )
                            return False
                    else:
                        logger.error(
                            f"Auth failed with status code {status_code}: {text}"
                        )
                        return False
        except Exception as e:
            logger.error(f"Auth failed with error: {e}")
            return False

    # 주식현재가 시세
    async def get_current_price(self, stock_no):
        try:
            if "KIS_ACCESS_TOKEN" not in os.environ:
                if not await self.auth():
                    # print("Failed to get access token")
                    return None

            headers = {
                "content-type": "application/json",
                "authorization": f"Bearer {os.environ['KIS_ACCESS_TOKEN']}",
                "appkey": os.getenv("KIS_APP_KEY"),
                "appsecret": os.getenv("KIS_APP_SECRET"),
                "tr_id": "FHKST01010100",
            }
            params = {
                "fid_cond_mrkt_div_code": "J",
                "fid_input_iscd": stock_no,
            }
            PATH = "uapi/domestic-stock/v1/quotations/inquire-price"
            URL = f"{URL_BASE}/{PATH}"

            # print(f"Price request URL: {URL}")
            # print(f"Price request headers: {headers}")
            # print(f"Price request params: {params}")

            async with aiohttp.ClientSession() as session:
                async with session.get(URL, headers=headers, params=params) as res:
                    status_code = res.status
                    text = await res.text()

                    # print(f"Price response status: {status_code}")
                    # print(f"Price response body: {text}")

                    if status_code == 500 and "기간이 만료된 token" in text:
                        if not await self.auth():
                            # print("Failed to refresh token")
                            return None

                        headers["authorization"] = (
                            f"Bearer {os.environ['KIS_ACCESS_TOKEN']}"
                        )
                        async with session.get(
                            URL, headers=headers, params=params
                        ) as res_refresh:
                            status_code = res_refresh.status
                            text = await res_refresh.text()

                            # print(
                            #     f"Price response status (after token refresh): {status_code}"
                            # )
                            # print(f"Price response body (after token refresh): {text}")

                    if status_code != 200:
                        # print(f"API call failed with status code {status_code}: {text}")
                        return None

                    try:
                        data = (
                            await res.json() if status_code == 200 else json.loads(text)
                        )
                        if data.get("rt_cd") != "0":
                            # print(f"API returned error: {data}")
                            return None

                        output = data.get("output", {})
                        if not output:
                            # print("No output data in response")
                            return None

                        # 필요한 정보만 추출하여 반환
                        return {
                            "대표 시장 한글 명": output.get("rprs_mrkt_kor_name", ""),
                            "업종": output.get("bstp_kor_isnm", ""),
                            "종목 코드": stock_no,
                            "주식 현재가": output.get("stck_prpr", ""),
                            "주식 전일 종가": output.get("stck_sdpr", ""),
                            "상한가": output.get("stck_mxpr", ""),
                            "하한가": output.get("stck_llam", ""),
                            "최고가": output.get("stck_hgpr", ""),
                            "최저가": output.get("stck_lwpr", ""),
                            "거래량": output.get("acml_vol", ""),
                            "누적 거래 대금": output.get("acml_tr_pbmn", ""),
                            "PER (주가수익비율)": output.get("per", ""),
                            "PBR (주가순자산비율)": output.get("pbr", ""),
                            "EPS (주당순이익)": output.get("eps", ""),
                            "BPS (주당순자산)": output.get("bps", ""),
                            "배당수익률": output.get("vol_tnrt", ""),
                            "전일 대비": output.get("prdy_vrss", ""),
                            "전일 대비 거래량 비율": output.get(
                                "prdy_vrss_vol_rate", ""
                            ),
                            "최고가 대비 현재가": f"{output.get('stck_hgpr', '')} - {output.get('stck_prpr', '')}",
                            "최저가 대비 현재가": f"{output.get('stck_prpr', '')} - {output.get('stck_lwpr', '')}",
                            "250일 최고가": output.get("d250_hgpr", ""),
                            "250일 최저가": output.get("d250_lwpr", ""),
                            "신용 가능 여부": output.get("crdt_able_yn", ""),
                            "ELW 발행 여부": output.get("elw_pblc_yn", ""),
                            "외국인 보유율": output.get("hts_frgn_ehrt", ""),
                            "단기과열 여부": output.get("ovtm_vi_cls_code", ""),
                            "저유동성 종목 여부": output.get("sltr_yn", ""),
                            "시장 경고 코드": output.get("mrkt_warn_cls_code", ""),
                        }
                    except (KeyError, json.JSONDecodeError) as e:
                        # print(f"Failed to parse price response: {e}\nResponse: {text}")
                        return None
        except Exception as e:
            # print(f"API call error: {str(e)}")
            return None

    def _run(
        self,
        stock_code: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        # 동기 버전에서는 비동기 함수를 asyncio.run으로 실행
        return asyncio.run(self._arun(stock_code, run_manager))

    async def _arun(
        self,
        stock_code: str,
        config: Optional[RunnableConfig] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ):
        if config and "tracer" in config["configurable"]:
            span = config["configurable"]["tracer"].span(name="analysis_stock", input=stock_code)
        else:
            span = None

        # 비동기 버전에서는 직접 비동기 함수 호출
        res = await self.get_current_price(stock_code)
        if res is None:
            res = {"error": "주가 정보를 가져오는데 실패했습니다."}

        if span:
            span.end(output=res)

        return res


class PredictStockTool(BaseTool):
    name: str = "predict_stock"
    description: str = (
        "This tool predicts stock price trends and analyzes future market movements based on stock price fluctuations. "
        "It identifies key trends, turning points, and factors that could influence future market performance. "
        "Use this tool to gain insights into market dynamics and formulate data-driven investment strategies."
    )
    args_schema: Type[BaseModel] = AnalysisStockInput
    return_direct: bool = False

    def predict_with_prophet(self, df: pd.DataFrame, periods: int = 365):
        """Prophet을 사용한 주가 예측"""

        prophet_df = pd.DataFrame({"ds": df["Date"], "y": df["Change"]})

        model = Prophet(
            daily_seasonality=True,
            weekly_seasonality=True,
            yearly_seasonality=True,
            changepoint_prior_scale=0.05,
        )
        model.fit(prophet_df)

        future = model.make_future_dataframe(periods=periods)
        forecast = model.predict(future)
        changes = forecast["yhat"].iloc[-periods:].values

        return changes

    def predict_with_arima(self, df: pd.DataFrame, periods: int = 365):
        """ARIMA를 사용한 주가 예측"""

        model = ARIMA(df["Change"], order=(5, 1, 0))
        results = model.fit()
        forecast = results.forecast(steps=periods).values

        return forecast

    def ensemble_prediction(self, stock_code: str, periods: int = 365):
        """Prophet과 ARIMA의 앙상블 예측"""

        df = fdr.DataReader(f"KRX:{stock_code}", "2023")["Change"]
        df = df.reset_index()

        prophet_changes = self.predict_with_prophet(df, periods)
        arima_changes = self.predict_with_arima(df, periods)

        ensemble_changes = (prophet_changes + arima_changes) / 2

        return ensemble_changes

    def _run(
        self, stock_code: str, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        try:

            # 앙상블 예측 실행
            predicted_changes = self.ensemble_prediction(stock_code)
            # print(predicted_changes)

            avg_change = np.mean(predicted_changes)
            max_change = np.max(predicted_changes)
            min_change = np.min(predicted_changes)
            volatility = np.std(predicted_changes)

            observation = {
                "평균 변동률": avg_change,
                "최대 상승률": max_change,
                "최대 하락률": min_change,
                "변동성": volatility
            }

            return observation

        except Exception as e:
            return f"예측 중 오류가 발생했습니다: {str(e)}"

    async def _arun(
        self,
        stock_code: str,
        config: Optional[RunnableConfig] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        if config and "tracer" in config["configurable"]:
            span = config["configurable"]["tracer"].span(name="predict_stock", input=stock_code)
        else:
            span = None

        result = self._run(stock_code)

        if span:
            span.end(output=result)

        return result
