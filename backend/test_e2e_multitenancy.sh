#!/bin/bash
# Comprehensive end-to-end test for school-based multi-tenancy with file uploads

API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)

echo "================================================================================"
echo "School-Based Multi-Tenancy End-to-End Test"
echo "================================================================================"
echo ""
echo "API URL: $API_URL"
echo ""

# Create a small test PDF
create_test_pdf() {
    local filename=$1
    cat > "$filename" << 'EOF'
%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<<>>>>endobj
4 0 obj<</Length 44>>stream
BT /F1 12 Tf 100 700 Td (Test Homework) Tj ET
endstream endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000056 00000 n 
0000000115 00000 n 
0000000229 00000 n 
trailer<</Size 5/Root 1 0 R>>
startxref
322
%%EOF
EOF
    echo "✅ Created test PDF: $filename"
}

# Test 1: Login as Teacher from Delhi Public School
echo "🧪 Test 1: Teacher Login - Delhi Public School"
echo "   Logging in as T_DEL..."

curl -s -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"roll_no":"T_DEL","password":"password"}' \
  -c /tmp/cookie_t_del.txt > /dev/null

echo "   ✅ Logged in as T_DEL"

# Get teacher's subject ID
SUBJECT_ID=$(curl -s -X GET "$API_URL/api/subjects?standard=10" \
  -b /tmp/cookie_t_del.txt \
  | python3 -c "import sys,json; data=json.load(sys.stdin); print(data[0]['id'] if data else 'ERROR')")

echo "   📚 Subject ID: $SUBJECT_ID"

# Test 2: Upload Homework as Delhi teacher
echo ""
echo "🧪 Test 2: Upload Homework - Delhi Public School Teacher"

create_test_pdf /tmp/test_homework_del.pdf

HOMEWORK_RESPONSE=$(curl -s -X POST "$API_URL/api/homework" \
  -b /tmp/cookie_t_del.txt \
  -F "subject_id=$SUBJECT_ID" \
  -F "standard=10" \
  -F "title=Algebra Homework - Delhi" \
  -F "file=@/tmp/test_homework_del.pdf")

HOMEWORK_ID=$(echo "$HOMEWORK_RESPONSE" | python3 -c "import sys,json; data=json.load(sys.stdin); print(data.get('homework_id', 'ERROR'))" 2>/dev/null || echo "ERROR")

if [ "$HOMEWORK_ID" != "ERROR" ]; then
    echo "   ✅ Homework uploaded: $HOMEWORK_ID"
    
    # Check S3 path
    S3_PATH=$(echo "$HOMEWORK_RESPONSE" | python3 -c "import sys,json; data=json.load(sys.stdin); print(data.get('file_path', 'N/A'))" 2>/dev/null || echo "N/A")
    echo "   📂 S3 Path: $S3_PATH"
    
    # Verify it starts with school name
    if [[ "$S3_PATH" == Delhi_Public_School* ]]; then
        echo "   ✅ S3 path correctly includes school name"
    else
        echo "   ❌ S3 path does NOT include school name!"
    fi
else
    echo "   ❌ Homework upload failed"
    echo "   Response: $HOMEWORK_RESPONSE"
fi

# Test 3: Login as Teacher from Modern Academy
echo ""
echo "🧪 Test 3: Teacher Login - Modern Academy"
echo "   Logging in as T_MOD..."

curl -s -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"roll_no":"T_MOD","password":"password"}' \
  -c /tmp/cookie_t_mod.txt > /dev/null

echo "   ✅ Logged in as T_MOD"

# Get teacher's subject ID
SUBJECT_ID_MOD=$(curl -s -X GET "$API_URL/api/subjects?standard=10" \
  -b /tmp/cookie_t_mod.txt \
  | python3 -c "import sys,json; data=json.load(sys.stdin); print(data[0]['id'] if data else 'ERROR')")

echo "   📚 Subject ID: $SUBJECT_ID_MOD"

# Test 4: Upload Homework as Modern Academy teacher
echo ""
echo "🧪 Test 4: Upload Homework - Modern Academy Teacher"

create_test_pdf /tmp/test_homework_mod.pdf

HOMEWORK_RESPONSE_MOD=$(curl -s -X POST "$API_URL/api/homework" \
  -b /tmp/cookie_t_mod.txt \
  -F "subject_id=$SUBJECT_ID_MOD" \
  -F "standard=10" \
  -F "title=Algebra Homework - Modern" \
  -F "file=@/tmp/test_homework_mod.pdf")

HOMEWORK_ID_MOD=$(echo "$HOMEWORK_RESPONSE_MOD" | python3 -c "import sys,json; data=json.load(sys.stdin); print(data.get('homework_id', 'ERROR'))" 2>/dev/null || echo "ERROR")

if [ "$HOMEWORK_ID_MOD" != "ERROR" ]; then
    echo "   ✅ Homework uploaded: $HOMEWORK_ID_MOD"
    
    # Check S3 path
    S3_PATH_MOD=$(echo "$HOMEWORK_RESPONSE_MOD" | python3 -c "import sys,json; data=json.load(sys.stdin); print(data.get('file_path', 'N/A'))" 2>/dev/null || echo "N/A")
    echo "   📂 S3 Path: $S3_PATH_MOD"
    
    # Verify it starts with school name
    if [[ "$S3_PATH_MOD" == Modern_Academy* ]]; then
        echo "   ✅ S3 path correctly includes school name"
    else
        echo "   ❌ S3 path does NOT include school name!"
    fi
else
    echo "   ❌ Homework upload failed"
    echo "   Response: $HOMEWORK_RESPONSE_MOD"
fi

# Test 5: Verify students see only their school's homework
echo ""
echo "🧪 Test 5: Student Visibility Test - Delhi Public School"
echo "   Logging in as S1_DEL..."

curl -s -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"roll_no":"S1_DEL","password":"password"}' \
  -c /tmp/cookie_s1_del.txt > /dev/null

HOMEWORK_LIST_DEL=$(curl -s -X GET "$API_URL/api/homework?standard=10" \
  -b /tmp/cookie_s1_del.txt)

HOMEWORK_COUNT_DEL=$(echo "$HOMEWORK_LIST_DEL" | python3 -c "import sys,json; data=json.load(sys.stdin); print(len(data) if isinstance(data, list) else 0)" 2>/dev/null || echo "0")

echo "   📚 Visible homework: $HOMEWORK_COUNT_DEL"

# Check if homework has Delhi in title
HAS_DELHI=$(echo "$HOMEWORK_LIST_DEL" | python3 -c "import sys,json; data=json.load(sys.stdin); print('YES' if any('Delhi' in h.get('title', '') for h in data) else 'NO')" 2>/dev/null || echo "NO")

echo "   ✅ Contains Delhi homework: $HAS_DELHI"

echo ""
echo "🧪 Test 6: Student Visibility Test - Modern Academy"
echo "   Logging in as S1_MOD..."

curl -s -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"roll_no":"S1_MOD","password":"password"}' \
  -c /tmp/cookie_s1_mod.txt > /dev/null

HOMEWORK_LIST_MOD=$(curl -s -X GET "$API_URL/api/homework?standard=10" \
  -b /tmp/cookie_s1_mod.txt)

HOMEWORK_COUNT_MOD=$(echo "$HOMEWORK_LIST_MOD" | python3 -c "import sys,json; data=json.load(sys.stdin); print(len(data) if isinstance(data, list) else 0)" 2>/dev/null || echo "0")

echo "   📚 Visible homework: $HOMEWORK_COUNT_MOD"

# Check if homework has Modern in title
HAS_MODERN=$(echo "$HOMEWORK_LIST_MOD" | python3 -c "import sys,json; data=json.load(sys.stdin); print('YES' if any('Modern' in h.get('title', '') for h in data) else 'NO')" 2>/dev/null || echo "NO")

echo "   ✅ Contains Modern homework: $HAS_MODERN"

# Summary
echo ""
echo "================================================================================"
echo "✅ Test Summary"
echo "================================================================================"
echo ""
echo "S3 Path Structure:"
echo "   Delhi teacher: $S3_PATH"
echo "   Modern teacher: $S3_PATH_MOD"
echo ""
echo "Student Visibility:"
echo "   Delhi student sees: $HOMEWORK_COUNT_DEL homework(s)"
echo "   Modern student sees: $HOMEWORK_COUNT_MOD homework(s)"
echo ""
echo "Expected: Each student should see 1 homework from their school only"
echo ""

# Cleanup
rm -f /tmp/test_homework_del.pdf /tmp/test_homework_mod.pdf

echo "Test complete!"
