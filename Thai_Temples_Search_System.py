from flask import Flask, request
from markupsafe import escape
from flask import render_template
from elasticsearch import Elasticsearch
import math
import re  # Import regex module for preprocessing


# Change pasword
ELASTIC_PASSWORD = "+NCV4QxneuKBVcl4xuhq"

es = Elasticsearch("https://localhost:9200", http_auth=("elastic", ELASTIC_PASSWORD), verify_certs=False)
app = Flask(__name__)

INDEX_NAME = "final_temple_tokenized"

def delete_index(index_name):
    """Delete the existing index if it exists."""
    if es.indices.exists(index=index_name):
        es.indices.delete(index=index_name)
        print(f"Index '{index_name}' deleted.")

def recreate_index_with_correct_mapping():
    # Define the new index settings and mappings
    settings = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "names_analyzer": {  # Search-time analyzer
                        "tokenizer": "icu_tokenizer",
                        "filter": [
                            "lowercase",
                            "names_synonyms"  # Search-time synonym filter
                        ]
                    },
                    "default_index_analyzer": {  # Index-time analyzer without synonyms
                        "tokenizer": "icu_tokenizer",
                        "filter": [
                            "lowercase"
                        ]
                    }
                },
                "filter": {
                    "names_synonyms": {
                        "type": "synonym_graph",  # Use synonym_graph for search-time
                        "synonyms": ["กรุงเทพฯ, กทม, กรุงเทพ, กรุงเทพมหานคร",
                                     "พระนครศรีอยุธยา, อยุธยา",
                                     "วัดใหญ่,วัดพระศรีรัตนมหาธาตุราชวรมหาวิหาร"],
                        "updateable": True
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "ชื่อวัด": {"type": "keyword"},
                "คำอธิบาย": {"type": "text"}, 
                "จังหวัด": {"type": "keyword"},
                "รูป": {"type": "keyword"},
                "เขต/อำเภอ": {"type": "keyword"},
                "แขวง/ตำบล": {"type": "keyword"},
                "ปีที่ก่อตั้ง": {"type": "keyword"},
                "tokenized_text": {"type": "text"}  
            }
        }
    }

    # Delete the existing index if it exists
    delete_index(INDEX_NAME)

    # Create the new index with the correct settings and mappings
    es.indices.create(index=INDEX_NAME, body=settings)


def tokenize_and_index_documents():
    original_index = "temple"  # Replace with your source index
    # Get all documents from the original 'temple' index
    res = es.search(index=original_index, body={"query": {"match_all": {}}}, size=1000)  # Adjust size as needed

    # Iterate through each document, tokenize, and add to new index
    for hit in res['hits']['hits']:
        doc_id = hit['_id']
        source = hit['_source']
        text = f"{source.get('ชื่อวัด', '')} {source.get('คำอธิบาย', '')} {source.get('จังหวัด', '')}"

        # Tokenize the document's text using icu_tokenizer
        body = {
            "tokenizer": "icu_tokenizer",
            "text": text
        }
        analysis_result = es.indices.analyze(index=original_index, body=body)
        tokens = ' '.join([token['token'] for token in analysis_result['tokens']])

        # Prepare the document for the new index with tokenized text
        new_doc = {
            "ชื่อวัด": source.get("ชื่อวัด"),
            "คำอธิบาย": source.get("คำอธิบาย"),
            "จังหวัด": source.get("จังหวัด"),
            "รูป": source.get("รูป"),
            "เขต/อำเภอ": source.get("เขต/อำเภอ"),
            "แขวง/ตำบล": source.get("แขวง/ตำบล"),
            'ปีที่ก่อตั้ง': source.get('ปีที่ก่อตั้ง'),
            "tokenized_text": tokens
        }

        # Index the new document into 'final_temple_tokenized'
        es.index(index="final_temple_tokenized", id=doc_id, body=new_doc)


@app.route('/')
def index():
    page_size = 10  # Show only X documents
    page_no = int(request.args.get('page', 1))  # Current page number (default to 1)
    
    body={
        "size": page_size,
        'from': page_size * (page_no-1),
        "query": {
            "match_all": {}
        },
        "sort": [
                {"จังหวัด": {"order": "asc"}}, 
                {"ชื่อวัด": {"order": "asc"}}
        ],
    }
    res = es.search(index=INDEX_NAME, body=body)

    hits = [
        {
            'ชื่อวัด': doc['_source'].get('ชื่อวัด', ''),
            'คำอธิบาย': doc['_source'].get('คำอธิบาย', ''),
            'จังหวัด': doc['_source'].get('จังหวัด', ''),
            'ปีที่ก่อตั้ง': doc['_source'].get('ปีที่ก่อตั้ง', ''),
            'รูป': doc['_source'].get('รูป', ''),
            'เขต/อำเภอ': doc['_source'].get('เขต/อำเภอ', ''),
            'แขวง/ตำบล': doc['_source'].get('แขวง/ตำบล', ''),
        }
        for doc in res['hits']['hits']
    ]

    total_results = res['hits']['total']['value']
    page_total = math.ceil(total_results / page_size) 

    return render_template('index.html', hits=hits, page_no=page_no, page_total=page_total, total_results=total_results) 






@app.route('/search')
def search():
    Real_keyword = request.args.get('keyword', '')  # Search keyword

    # Remove "วัดใน" if present
    keyword = re.sub(r'^(วัดใน)', '', Real_keyword).strip()


    # ======================= Match search in ชื่อวัด =======================
    exact_match_query = {"match_phrase": {"ชื่อวัด": keyword}}
    print(f"1temple__{exact_match_query}")
    exact_match_res = es.search(index='final_temple_tokenized', body={"query": exact_match_query})

    if exact_match_res['hits']['total']['value'] > 0:
        hits = [
            {
                'ชื่อวัด': doc['_source'].get('ชื่อวัด', ''),
                'คำอธิบาย': doc['_source'].get('คำอธิบาย', ''),
                'จังหวัด': doc['_source'].get('จังหวัด', ''),
                'ปีที่ก่อตั้ง': doc['_source'].get('ปีที่ก่อตั้ง', ''),
                'รูป': doc['_source'].get('รูป', ''),
                'เขต/อำเภอ': doc['_source'].get('เขต/อำเภอ', ''),
                'แขวง/ตำบล': doc['_source'].get('แขวง/ตำบล', ''),
                '_score': doc.get('_score', 0)
            }
            for doc in exact_match_res['hits']['hits']
        ]

        return render_template('index.html', keyword=keyword, Real_keyword=Real_keyword, hits=hits, page_no=1, page_total=1, total_results=1)

   
   # ======================= Match search in every postion จังหวัด =======================
    if "จังหวัด" in Real_keyword:
        # List of all 77 provinces in Thailand
        provinces = [
            'กรุงเทพมหานคร', 'กระบี่', 'กาญจนบุรี', 'กาฬสินธุ์', 'กำแพงเพชร', 'ขอนแก่น', 'จันทบุรี', 'ฉะเชิงเทรา', 'ชลบุรี',
            'ชัยนาท', 'ชัยภูมิ', 'ชุมพร', 'เชียงราย', 'เชียงใหม่', 'ตรัง', 'ตราด', 'ตาก', 'นครนายก', 'นครปฐม', 'นครพนม',
            'นครราชสีมา', 'นครศรีธรรมราช', 'นครสวรรค์', 'นราธิวาส', 'น่าน', 'บึงกาฬ', 'บุรีรัมย์', 'ปทุมธานี', 'ประจวบคีรีขันธ์',
            'ปัตตานี', 'พะเยา', 'พระนครศรีอยุธยา', 'พังงา', 'พัทลุง', 'พิจิตร', 'พิษณุโลก', 'ภูเก็ต', 'มหาสารคาม',
            'มุกดาหาร', 'ยะลา', 'ยโสธร', 'ร้อยเอ็ด', 'ระนอง', 'ระยอง', 'ราชบุรี', 'ลพบุรี', 'ลำปาง', 'ลำพูน', 'เลย',
            'ศรีสะเกษ', 'สกลนคร', 'สงขลา', 'สมุทรปราการ', 'สมุทรสงคราม', 'สมุทรสาคร', 'สระแก้ว', 'สระบุรี', 'สิงห์บุรี',
            'สุโขทัย', 'สุพรรณบุรี', 'สุราษฎร์ธานี', 'สุรินทร์', 'สตูล', 'หนองคาย', 'หนองบัวลำภู', 'อ่างทอง', 'อำนาจเจริญ',
            'อุดรธานี', 'อุตรดิตถ์', 'อุบลราชธานี', 'อำนาจเจริญ', 'เชียงใหม่', 'สงขลา', 'นราธิวาส',
            'กทม' , 'กรุงเทพฯ' , 'กรุงเทพ' , 'อยุธยา'
            
        ]


        # Create a regex pattern to match any of the provinces
        province_pattern = '|'.join(provinces)  # Combine all provinces into a single regex pattern
        province_keywords = re.findall(province_pattern, keyword)  # Modify this regex to capture more keywords

        print(f"2province__{province_keywords}")

        if province_keywords:  # Ensure there's something to search
            # Create a query for each province found in the input keyword
            province_match_query = {
                "query": {
                    "bool": {
                        "should": [
                            {
                                "match": {
                                    "จังหวัด": {
                                        "query": province,
                                        "analyzer": "names_analyzer"  # Use the analyzer with synonyms
                                    }
                                }
                            } for province in province_keywords
                        ]
                    }
                },
                "sort": [{"ชื่อวัด": {"order": "asc"}}]
            }

            province_match_res = es.search(index='final_temple_tokenized', body=province_match_query)

            if province_match_res['hits']['total']['value'] > 0:
                hits = [
                    {
                        'ชื่อวัด': doc['_source'].get('ชื่อวัด', ''),
                        'คำอธิบาย': doc['_source'].get('คำอธิบาย', ''),
                        'จังหวัด': doc['_source'].get('จังหวัด', ''),
                        'ปีที่ก่อตั้ง': doc['_source'].get('ปีที่ก่อตั้ง', ''),
                        'รูป': doc['_source'].get('รูป', ''),
                        'เขต/อำเภอ': doc['_source'].get('เขต/อำเภอ', ''),
                        'แขวง/ตำบล': doc['_source'].get('แขวง/ตำบล', ''),
                        '_score': doc.get('_score', 0)
                    }
                    for doc in province_match_res['hits']['hits']
                ]
                return render_template('index.html', keyword=keyword, Real_keyword=Real_keyword, hits=hits, page_no=1, page_total=1, total_results=len(hits))


  # ======================= Match search in เขต/อำเภอ =======================
    if "เขต" in Real_keyword or "อำเภอ" in Real_keyword:
        # Check which term is present in the Real_keyword and extract the part of the query
        if "เขต" in Real_keyword:
            district_keyword = Real_keyword.split("เขต", 1)[1].strip()  # Get the text after "เขต"
        elif "อำเภอ" in Real_keyword:
            district_keyword = Real_keyword.split("อำเภอ", 1)[1].strip()  # Get the text after "อำเภอ"

        print(f"3district__{district_keyword}")

        if district_keyword:  # Ensure there's something to search
            # Use names_analyzer that includes synonyms filter for more accurate search
            district_match_query = {
                "query": {
                    "match": {
                        "เขต/อำเภอ": {
                            "query": district_keyword,
                            "analyzer": "names_analyzer"  # Use the analyzer with synonyms
                        }
                    }
                },
                "sort": [{"ชื่อวัด": {"order": "asc"}}]
            }

            # Search the index using the modified query
            district_match_res = es.search(index='final_temple_tokenized', body=district_match_query)

            if district_match_res['hits']['total']['value'] > 0:
                hits = [
                    {
                        'ชื่อวัด': doc['_source'].get('ชื่อวัด', ''),
                        'คำอธิบาย': doc['_source'].get('คำอธิบาย', ''),
                        'จังหวัด': doc['_source'].get('จังหวัด', ''),
                        'ปีที่ก่อตั้ง': doc['_source'].get('ปีที่ก่อตั้ง', ''),
                        'รูป': doc['_source'].get('รูป', ''),
                        'เขต/อำเภอ': doc['_source'].get('เขต/อำเภอ', ''),
                        'แขวง/ตำบล': doc['_source'].get('แขวง/ตำบล', ''),
                        '_score': doc.get('_score', 0)
                    }
                    for doc in district_match_res['hits']['hits']
                ]
                return render_template('index.html', keyword=district_keyword, Real_keyword=Real_keyword, hits=hits, page_no=1, page_total=1, total_results=len(hits))

    # ======================= Match search in แขวง/ตำบล =======================
    if "แขวง" in Real_keyword or "ตำบล" in Real_keyword:
        # Check which term is present in the Real_keyword and extract the part of the query
        if "แขวง" in Real_keyword:
            subdistrict_keyword = Real_keyword.split("แขวง", 1)[1].strip()  # Get the text after "แขวง"
        elif "ตำบล" in Real_keyword:
            subdistrict_keyword = Real_keyword.split("ตำบล", 1)[1].strip()  # Get the text after "ตำบล"
        print(f"4subdistrict__{subdistrict_keyword}")


        if subdistrict_keyword:  # Ensure there's something to search
            # Use names_analyzer that includes synonyms filter for more accurate search
            subdistrict_match_query = {
                "query": {
                    "match": {
                        "แขวง/ตำบล": {
                            "query": subdistrict_keyword,
                            "analyzer": "names_analyzer"  # Use the analyzer with synonyms
                        }
                    }
                },
                "sort": [{"ชื่อวัด": {"order": "asc"}}]
            }

            # Search the index using the modified query
            subdistrict_match_res = es.search(index='final_temple_tokenized', body=subdistrict_match_query)

            if subdistrict_match_res['hits']['total']['value'] > 0:
                hits = [
                    {
                        'ชื่อวัด': doc['_source'].get('ชื่อวัด', ''),
                        'คำอธิบาย': doc['_source'].get('คำอธิบาย', ''),
                        'จังหวัด': doc['_source'].get('จังหวัด', ''),
                        'ปีที่ก่อตั้ง': doc['_source'].get('ปีที่ก่อตั้ง', ''),
                        'รูป': doc['_source'].get('รูป', ''),
                        'เขต/อำเภอ': doc['_source'].get('เขต/อำเภอ', ''),
                        'แขวง/ตำบล': doc['_source'].get('แขวง/ตำบล', ''),
                        '_score': doc.get('_score', 0)
                    }
                    for doc in subdistrict_match_res['hits']['hits']
                ]
                return render_template('index.html', keyword=subdistrict_keyword, Real_keyword=Real_keyword, hits=hits, page_no=1, page_total=1, total_results=len(hits))


    # ======================= Multi_match =======================
    page_size = 10  # Show only X documents
    page_no = int(request.args.get('page', 1))  # Current page number (default to 1)
    
    # Step 2: Fallback to multi-field search if no exact match
    if Real_keyword.strip() == "วัด":
        keyword = Real_keyword.strip()  # If the keyword is just "วัด", keep it as is
    else:
        # Remove all occurrences of "วัด" anywhere in the string
        keyword = re.sub(r'วัด', '', keyword).strip()

        print("*********")  
        print(f"5multi__{keyword}")
        print("*********")  

    body = {
        "size": 10,
        'from': page_size * (page_no-1),
        "query": {
            "bool": {
                "should": [
                    {
                        "multi_match": {
                            "query": keyword,
                            "fields": ["ชื่อวัด^1000", "ปีที่ก่อตั้ง^10", "คำอธิบาย^0.1", "จังหวัด", "แขวง/ตำบล", "เขต/อำเภอ", "tokenized_text"],
                            "analyzer": "names_analyzer",
                            "fuzziness": "auto",
                            "fuzzy_transpositions": True,
                            "slop": 2
                        }
                    }
                ],
                "minimum_should_match": 1
            }
        }
    }
    res = es.search(index='final_temple_tokenized', body=body)

    hits = [
        {
            'ชื่อวัด': doc['_source'].get('ชื่อวัด', ''),
            'คำอธิบาย': doc['_source'].get('คำอธิบาย', ''),
            'จังหวัด': doc['_source'].get('จังหวัด', ''),
            'ปีที่ก่อตั้ง': doc['_source'].get('ปีที่ก่อตั้ง', ''),
            'รูป': doc['_source'].get('รูป', ''),
            'เขต/อำเภอ': doc['_source'].get('เขต/อำเภอ', ''),
            'แขวง/ตำบล': doc['_source'].get('แขวง/ตำบล', ''),
            '_score': doc.get('_score', 0)  # Include the _score in the result
        }
        for doc in res['hits']['hits']  # Get actual data from the search results
    ]

    total_results = res['hits']['total']['value']
    page_total = math.ceil(total_results / page_size)

    # Return the results to the template
    return render_template('index.html', keyword=keyword, Real_keyword=Real_keyword, hits=hits, page_no=page_no, page_total=page_total, total_results=total_results) 






# Main execution flow
if __name__ == "__main__":
    delete_index(INDEX_NAME)  # Step 1: Delete the existing index
    recreate_index_with_correct_mapping()  # Step 2: Create a fresh index
    tokenize_and_index_documents()  # Step 3: Re-index the data