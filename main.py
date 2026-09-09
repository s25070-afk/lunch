import streamlit as st
import requests
import calendar
import re
from datetime import datetime

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 기본 데이터 정의
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="학교 급식 식단 달력",
    page_icon="🍱",
    layout="wide"
)

# NEIS API에서 사용하는 알레르기 번호 매핑 테이블 (1~19번)
ALLERGY_MAP = {
    "1": "난류", "2": "우유", "3": "메밀", "4": "땅콩", "5": "대두",
    "6": "밀", "7": "게", "8": "새우", "9": "돼지고기", "10": "복숭아",
    "11": "토마토", "12": "아황산류", "13": "호두", "14": "닭고기",
    "15": "쇠고기", "16": "오징어", "17": "조개류", "18": "잣", "19": "새우"
}

# -----------------------------------------------------------------------------
# 2. 헬퍼 함수 정의
# -----------------------------------------------------------------------------
def transform_allergy(menu_str, convert_to_name=False):
    """
    메뉴 문자열 내의 알레르기 번호를 숫자로 유지하거나 식품명으로 변환합니다.
    예: "미역국1.5.6." -> "미역국(난류, 대두, 밀)" 또는 "미역국(1, 5, 6)"
    """
    def replace_allergy(match):
        numbers = re.findall(r'\d+', match.group())
        if not numbers:
            return ""
        if convert_to_name:
            names = [ALLERGY_MAP.get(num, num) for num in numbers]
            return f" <span style='color: #888; font-size: 0.8em;'>({', '.join(names)})</span>"
        else:
            return f" <span style='color: #888; font-size: 0.8em;'>({'.'.join(numbers)})</span>"

    # 메뉴 이름 뒤의 숫자.숫자. 패턴을 찾아서 변환
    cleaned_menu = re.sub(r'(\.\d+)+\.?', replace_allergy, menu_str)
    # API 응답 내 태그 제거 및 정리
    cleaned_menu = cleaned_menu.replace("<br/>", "\n").strip()
    return cleaned_menu

@st.cache_data(ttl=3600)
def fetch_meal_data(api_key, edu_code, school_code, from_date, to_date):
    """
    NEIS 오픈 API를 통해 한 달치 급식 데이터를 조회합니다. (API 통신 에러 처리 포함)
    """
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "KEY": api_key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "ATPT_OFCDC_SC_CODE": edu_code,
        "SD_SCHUL_CODE": school_code,
        "MLSV_FROM_YMD": from_date,
        "MLSV_TO_YMD": to_date
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # NEIS API 응답 예외 처리
        if "mealServiceDietInfo" in data:
            return data["mealServiceDietInfo"][1]["row"], None
        elif "RESULT" in data:
            # 데이터가 없는 경우 (INFO-200 등)
            if data["RESULT"]["CODE"] == "INFO-200":
                return [], None
            return None, f"API 오류: {data['RESULT']['MESSAGE']} ({data['RESULT']['CODE']})"
        else:
            return [], None
            
    except requests.exceptions.RequestException as e:
        return None, f"API 통신 실패: 인터넷 연결 또는 NEIS 서버 상태를 확인하세요. ({e})"
    except Exception as e:
        return None, f"데이터 처리 중 오류 발생: {e}"

# -----------------------------------------------------------------------------
# 3. 사이드바 구성 (설정 및 정보)
# -----------------------------------------------------------------------------
st.sidebar.header("⚙️ 학교 및 식단 설정")

# API Key 검증
if "NEIS_KEY" not in st.secrets or not st.secrets["NEIS_KEY"]:
    st.error("🔑 NEIS API 키가 설정되지 않았습니다.")
    st.info("`.streamlit/secrets.toml` 파일에 `NEIS_KEY = '발급받은키'`를 작성 후 다시 실행해 주세요.")
    st.stop()

neis_api_key = st.secrets["NEIS_KEY"]

# 학교 정보 입력 (기본값: 서울특별시교육청 / 서울고등학교 예시)
edu_office_code = st.sidebar.text_input("시도교육청코드", value="B10", help="예: 서울 B10, 경기 J10 등")
school_code = st.sidebar.text_input("표준학교코드", value="7010536", help="7자리 표준학교코드 입력")

st.sidebar.markdown("---")

# 알레르기 표시 토글
convert_allergy = st.sidebar.toggle("알레르기 식품명으로 변환", value=False)

# 사이드바 알레르기 번호 매핑 안내 (접기)
with st.sidebar.expander("ℹ️ 알레르기 정보 번호 안내표"):
    for code, name in ALLERGY_MAP.items():
        st.write(f"**{code}**: {name}")

# -----------------------------------------------------------------------------
# 4. 메인 화면 상단 영역 (조회 조건 선택)
# -----------------------------------------------------------------------------
st.title("🍱 우리 학교 한 달 급식 달력")

col1, col2, col3 = st.columns([1, 1, 2])

current_year = datetime.now().year
current_month = datetime.now().month

with col1:
    selected_year = st.selectbox("연도 선택", range(current_year - 1, current_year + 2), index=1)

with col2:
    selected_month = st.selectbox("월 선택", range(1, 13), index=current_month - 1)

with col3:
    meal_filter = st.radio(
        "급식 종류",
        ["전체 보기", "중식만 보기", "석식만 보기"],
        horizontal=True
    )

st.markdown("---")

# -----------------------------------------------------------------------------
# 5. 데이터 패치 및 날짜별 딕셔너리 재구성
# -----------------------------------------------------------------------------
# 선택 월의 시작일과 말일 계산
_, last_day = calendar.monthrange(selected_year, selected_month)
from_ymd = f"{selected_year}{selected_month:02d}01"
to_ymd = f"{selected_year}{selected_month:02d}{last_day:02d}"

# API 호출
raw_meals, error_msg = fetch_meal_data(
    neis_api_key, edu_office_code, school_code, from_ymd, to_ymd
)

if error_msg:
    st.error(f"🚨 {error_msg}")
    st.stop()

# 날짜별로 식단 데이터를 그룹화하는 딕셔너리 {일(int): [식단정보, ...]}
daily_meals = {}
if raw_meals:
    for item in raw_meals:
        # YYYYMMDD 중 DD만 extraction
        day_num = int(item["MLSV_YMD"][-2:])
        if day_num not in daily_meals:
            daily_meals[day_num] = []
        daily_meals[day_num].append(item)

# -----------------------------------------------------------------------------
# 6. 달력 화면 구성 (화면 오류 처리 포함)
# -----------------------------------------------------------------------------
try:
    # 해당 월의 평일 달력 구조 생성 (월~금)
    cal = calendar.Calendar(firstweekday=0) # 0: 월요일
    month_days = cal.monthdayscalendar(selected_year, selected_month)

    # 평일(월~금) 데이터만 필터링
    weekday_calendar = []
    for week in month_days:
        week_days = week[:5] # 월, 화, 수, 목, 금만 선택
        if any(day != 0 for day in week_days): # 그 주에 이번 달 날짜가 하나라도 있는 경우만
            weekday_calendar.append(week_days)

    weekday_names = ["월", "화", "수", "목", "금"]
    today_str = datetime.now().strftime("%Y%m%d")

    # 달력 그리기
    for week in weekday_calendar:
        cols = st.columns(5)
        for idx, day in enumerate(week):
            with cols[idx]:
                if day == 0:
                    # 이번 달이 아닌 날짜 칸 (빈 카드)
                    st.markdown("""
                        <div style="border: 1px dashed #ddd; border-radius: 8px; padding: 10px; min-height: 180px; background-color: #fafafa;">
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    date_str = f"{selected_year}{selected_month:02d}{day:02d}"
                    is_today = (date_str == today_str)
                    
                    # 오늘 날짜 배지
                    today_badge = "<span style='background-color: #ff4b4b; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.7em;'>TODAY</span>" if is_today else ""
                    
                    header_html = f"<b>{selected_month}/{day} ({weekday_names[idx]})</b> {today_badge}"
                    
                    meal_content_html = ""
                    
                    if day in daily_meals:
                        meals_for_day = daily_meals[day]
                        displayed_count = 0
                        
                        for meal in meals_for_day:
                            meal_name = meal.get("MMEAL_SC_NM", "") # 조식, 중식, 석식
                            
                            # 급식 종류 필터링 적용
                            if meal_filter == "중식만 보기" and meal_name != "중식":
                                continue
                            if meal_filter == "석식만 보기" and meal_name != "석식":
                                continue

                            # 메뉴 라인 생성
                            dish_raw = meal.get("DDISH_NM", "")
                            dish_formatted = transform_allergy(dish_raw, convert_allergy)
                            
                            # 급식 종류별 식별 색상 적용 (중식: 파란색, 석식: 빨간색, 그외: 초록색)
                            if meal_name == "중식":
                                badge_color = "#1E88E5" # Blue
                            elif meal_name == "석식":
                                badge_color = "#E53935" # Red
                            else:
                                badge_color = "#43A047" # Green
                                
                            meal_content_html += f"""
                            <div style="margin-top: 8px;">
                                <span style="background-color: {badge_color}; color: white; padding: 1px 5px; border-radius: 3px; font-size: 0.75em; font-weight: bold;">
                                    {meal_name}
                                </span>
                                <div style="font-size: 0.85em; margin-top: 4px; line-height: 1.4; color: #333;">
                                    {dish_formatted.replace('\n', '<br/>')}
                                </div>
                            </div>
                            """
                            displayed_count += 1
                        
                        if displayed_count == 0:
                            meal_content_html = "<div style='color: #888; font-size: 0.8em; margin-top: 15px;'>해당 식단 없음</div>"
                    else:
                        meal_content_html = "<div style='color: #aaa; font-size: 0.8em; margin-top: 15px;'>급식 없음</div>"

                    # 카드 형태로 렌더링
                    st.markdown(f"""
                        <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 10px; min-height: 200px; background-color: white; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                            {header_html}
                            <hr style="margin: 6px 0; border: 0; border-top: 1px solid #eee;">
                            {meal_content_html}
                        </div>
                    """, unsafe_allow_html=True)

        st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"🖼️ 화면을 구성하는 도중 오류가 발생했습니다: {e}")
