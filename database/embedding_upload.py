# MongoDB에서 데이터 가져오기 및 중복 확인 후 MilvusDB에 데이터 적재

from pymongo import MongoClient
from pymilvus import Collection, MilvusClient
from tqdm import tqdm
import numpy as np
from FlagEmbedding import BGEM3FlagModel
from doc import Document


def convert_objectid(doc):
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
        
    if 'timestamp' in doc:
        doc['timestamp'] = int(doc['timestamp'].timestamp())

    return doc

def main():
    # MongoDB 연결
    mongo_client = MongoClient('localhost', port=27017)
    db = mongo_client['stockelper']
    news = db.news.find({})
    news = list(news)
    news = [convert_objectid(doc) for doc in news]
    print(f'Total News in MongoDB: {len(news)}')

    # MilvusDB 연결
    milvus_client = MilvusClient(uri='http://localhost:21001')
    collection = Collection("stockelper")

    # 임베딩 모델 초기화
    embedding_function = BGEM3FlagModel('BAAI/bge-m3', use_fp16=False, device='cuda')

    for data in tqdm(news):
        # MongoDB의 '_id'를 기준으로 중복 확인
        if not collection.query(expr=f"id == '{data['_id']}'"):
            tmp = f"title: {data['title']}\ncontent: {data['content']}"
            embedding = embedding_function.encode(tmp, return_dense=True, return_sparse=False, batch_size=24)
            data['embedding'] = np.array(embedding['dense_vecs']).tolist()  # 리스트로 변환

            # 배치에 데이터 추가
            data_batch.append(data)

            # 배치 크기만큼 데이터가 모이면 Milvus에 삽입
            if len(data_batch) >= batch_size:
                try:
                    res = milvus_client.insert(
                        collection_name="stockelper",
                        data=data_batch
                    )
                    data_batch = []  # 배치 초기화
                except Exception as e:
                    print(f"데이터 삽입 중 오류 발생: {e}")

    # 남은 데이터 삽입
    if data_batch:
        try:
            res = milvus_client.insert(
                collection_name="stockelper",
                data=data_batch
            )
        except Exception as e:
            print(f"데이터 삽입 중 오류 발생: {e}")

if __name__ == "__main__":
    main()