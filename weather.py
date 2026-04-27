import streamlit as st
import requests
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator
import platform

# 한글 폰트 설정 (OS 자동 감지)
system = platform.system()
if system == "Windows":
    plt.rcParams['font.family'] = 'Malgun Gothic'
elif system == "Darwin":  # macOS
    plt.rcParams['font.family'] = 'AppleGothic'
else:  # Linux 등 기타 OS
    plt.rcParams['font.family'] = 'DejaVu Sans'

# 마이너스 기호 깨짐 방지
plt.rcParams['axes.unicode_minus'] = False

# Streamlit 페이지 설정
st.set_page_config(page_title="서울 날씨 대시보드", page_icon="🌤️", layout="wide")

st.title("🚌 대중교통 이용자 전용 기상 케어 대시보드")
st.markdown("---")
st.markdown("##### 정류장 대기 중 날씨로 인한 불편함을 사전에 알려드립니다.")

# 날씨 이모지 매핑
weather_emojis = {
    "Clear": "☀️",
    "Clouds": "☁️",
    "Rain": "🌧️",
    "Drizzle": "🌦️",
    "Thunderstorm": "⛈️",
    "Snow": "❄️",
    "Mist": "🌫️",
    "Smoke": "💨",
    "Haze": "🌫️",
    "Dust": "🌪️",
    "Fog": "🌫️",
    "Sand": "🌪️",
    "Ash": "💨",
    "Squall": "💨",
    "Tornado": "🌪️"
}

# 실외 대기 쾌적도 계산 함수
# [Pain Point 해결] 정류장에서 느끼는 불편함을 수치화하여 대기 시간 계획 지원
def calculate_outdoor_comfort_index(temp, humidity, wind_speed, weather_desc):
    """
    실외 대기 쾌적도 지수 계산 (0~100점)
    - 온도: 16~24°C가 최적 (이탈할수록 감점)
    - 습도: 40~60%가 최적 (이탈할수록 감점)
    - 풍속: 0~5 m/s가 최적 (과도하면 감점)
    - 날씨: 맑음/구름 최고점, 비/눈/천둥 대폭 감점
    """
    score = 100
    
    # 온도 평가: 16~24°C 최적
    if temp < 0:
        score -= 30  # 매우 추움
    elif temp < 10:
        score -= 15  # 추움
    elif temp < 16:
        score -= 5   # 약간 추움
    elif temp > 30:
        score -= 25  # 매우 더움
    elif temp > 25:
        score -= 10  # 더움
    
    # 습도 평가: 40~60% 최적
    if humidity < 30 or humidity > 80:
        score -= 15
    elif humidity < 40 or humidity > 70:
        score -= 8
    
    # 풍속 평가: 5 m/s 이상 불쾌
    if wind_speed > 10:
        score -= 20
    elif wind_speed > 7:
        score -= 10
    elif wind_speed > 5:
        score -= 5
    
    # 날씨 평가
    if "rain" in weather_desc.lower() or "drizzle" in weather_desc.lower():
        score -= 25  # 비는 대기 불편
    elif "thunderstorm" in weather_desc.lower():
        score -= 35  # 뇌우는 매우 위험
    elif "snow" in weather_desc.lower():
        score -= 30  # 눈은 대기 어려움
    elif "fog" in weather_desc.lower() or "mist" in weather_desc.lower():
        score -= 10
    
    return max(0, min(100, score))  # 0~100 범위 유지

# 쾌적도 등급 판정 함수
# [Pain Point 해결] 숫자뿐만 아니라 직관적 등급 제시로 빠른 판단 지원
def get_comfort_level(score):
    """쾌적도 점수를 등급과 추천 메시지로 변환"""
    if score >= 80:
        return "최고", "🟢 정류장 대기 최적 상태", "#2ecc71"
    elif score >= 60:
        return "좋음", "🟡 약간의 불편함 예상", "#f39c12"
    elif score >= 40:
        return "보통", "🟠 대기 시 주의 필요", "#e74c3c"
    else:
        return "나쁨", "🔴 최대한 실내 대기 권장", "#c0392b"

# 도시별 위도/경도 및 한글명 매핑
cities_info = {
    "서울": {"code": "Seoul,KR", "lat": 37.5665, "lon": 126.9780},
    "부산": {"code": "Busan,KR", "lat": 35.1795, "lon": 129.0756},
    "제주": {"code": "Jeju,KR", "lat": 33.4996, "lon": 126.5312},
    "도쿄": {"code": "Tokyo,JP", "lat": 35.6762, "lon": 139.6503}
}

# 도시별 한글명 매핑
city_names_korean = {
    "서울": "서울, 대한민국",
    "부산": "부산, 대한민국",
    "제주": "제주, 대한민국",
    "도쿄": "도쿄, 일본"
}

# 사이드바에 설정 영역 구성
st.sidebar.header("⚙️ 설정")
api_key = st.sidebar.text_input(
    "OpenWeatherMap API 키 입력",
    type="password",
    help="https://openweathermap.org/ 에서 무료 API 키를 발급받으세요"
)

# 도시 선택 필터 추가: 사용자가 원하는 도시를 선택할 수 있도록 제공
selected_city = st.sidebar.selectbox(
    "📍 조회할 도시 선택",
    list(cities_info.keys()),
    index=0
)

if api_key:
    try:
        # 선택된 도시의 현재 날씨 데이터 조회
        city_code = cities_info[selected_city]["code"]
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city_code,
            "appid": api_key,
            "units": "metric"
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # 날씨 정보 추출
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        wind_speed = data["wind"]["speed"]
        weather_main = data["weather"][0]["main"]
        weather_desc = data["weather"][0]["description"]
        
        # 날씨에 맞는 이모지 선택
        weather_emoji = weather_emojis.get(weather_main, "🌤️")
        
        # 현재 날씨 정보 표시: 이모지와 기본 정보
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown(f"<h1 style='text-align: center; font-size: 120px;'>{weather_emoji}</h1>", unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"### 🌡️ 현재 온도: **{temp}°C**")
            st.markdown(f"### 🤔 체감 온도: **{feels_like}°C**")
            st.markdown(f"### 📝 날씨 상태: **{weather_desc.capitalize()}**")
        
        st.markdown("---")
        
        # 상세 기후 지표 표시
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        
        with metric_col1:
            st.metric("💧 습도", f"{humidity}%")
        
        with metric_col2:
            st.metric("💨 풍속", f"{wind_speed} m/s")
        
        with metric_col3:
            st.metric("🏙️ 위치", city_names_korean[selected_city])
        
        # 추가 기후 정보
        st.markdown("---")
        st.markdown("### 📊 추가 정보")
        
        add_col1, add_col2 = st.columns(2)
        
        with add_col1:
            if "clouds" in data:
                st.info(f"☁️ 구름 양: {data['clouds'].get('all', 'N/A')}%")
            if "visibility" in data:
                st.info(f"👁️ 시정: {data['visibility']/1000:.1f} km")
        
        with add_col2:
            if "pressure" in data["main"]:
                st.info(f"🔹 기압: {data['main']['pressure']} hPa")
            st.info(f"⏰ 업데이트 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        st.success("✅ 날씨 데이터를 성공적으로 불러왔습니다!")
        
        # 실외 대기 쾌적도 지수 계산 및 표시
        # [Pain Point 해결] 정류장 대기 시 숫자화된 불편함 지수로 대기 시간 계획 지원
        comfort_score = calculate_outdoor_comfort_index(temp, humidity, wind_speed, weather_desc)
        comfort_level, comfort_msg, comfort_color = get_comfort_level(comfort_score)
        
        st.markdown("---")
        st.markdown("### 🎯 정류장 대기 쾌적도 평가")
        
        # 쾌적도 지수를 시각적으로 표시하는 메트릭 및 메시지
        comfort_col1, comfort_col2 = st.columns([1, 2])
        
        with comfort_col1:
            st.metric("🌟 쾌적도 지수", f"{comfort_score}점", "만점 100점")
        
        with comfort_col2:
            st.markdown(f"<div style='background-color: {comfort_color}; padding: 15px; border-radius: 10px; color: white;'>"
                       f"<h4 style='margin: 0;'>{comfort_level} 등급</h4>"
                       f"<p style='margin: 5px 0 0 0;'>{comfort_msg}</p>"
                       f"</div>", unsafe_allow_html=True)
        
        # ==================== 동적 차트 구현 시작 ====================
        # Matplotlib를 사용하여 시간대별 기온 변화 및 쾌적도 변화를 선 그래프로 표시
        st.markdown("---")
        st.markdown("### 📈 시간대별 기온 및 쾌적도 변화")
        
        try:
            # OpenWeatherMap의 5일 예보 API를 사용하여 시간대별 데이터 조회
            forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
            forecast_params = {
                "q": city_code,
                "appid": api_key,
                "units": "metric"
            }
            
            forecast_response = requests.get(forecast_url, params=forecast_params)
            forecast_response.raise_for_status()
            forecast_data = forecast_response.json()
            
            # 시간대별 온도 및 쾌적도 데이터 추출
            times = []
            temps = []
            feels_likes = []
            comfort_indices = []
            
            for item in forecast_data["list"][:16]:  # 최대 16개 시간 데이터 (5일 중 처음 2일)
                time_str = item["dt_txt"]
                time_obj = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                times.append(time_obj)
                temps.append(item["main"]["temp"])
                feels_likes.append(item["main"]["feels_like"])
                
                # 시간대별 쾌적도 지수 계산
                forecast_temp = item["main"]["temp"]
                forecast_humidity = item["main"]["humidity"]
                forecast_wind_speed = item["wind"]["speed"]
                forecast_weather_desc = item["weather"][0]["description"]
                comfort_idx = calculate_outdoor_comfort_index(forecast_temp, forecast_humidity, forecast_wind_speed, forecast_weather_desc)
                comfort_indices.append(comfort_idx)
            
            # Matplotlib을 사용한 2개의 선 그래프 생성
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
            
            # 첫 번째 그래프: 기온과 체감온도
            ax1.plot(times, temps, marker='o', linewidth=2.5, markersize=6, label='현재 기온', color='#FF6B6B')
            ax1.plot(times, feels_likes, marker='s', linewidth=2.5, markersize=6, label='체감 기온', color='#4ECDC4', linestyle='--')
            
            # 첫 번째 그래프 스타일 설정
            ax1.set_xlabel('시간', fontsize=12, fontweight='bold')
            ax1.set_ylabel('온도 (°C)', fontsize=12, fontweight='bold')
            ax1.set_title(f'{selected_city} - 시간대별 기온 변화', fontsize=14, fontweight='bold', pad=20)
            ax1.grid(True, alpha=0.3, linestyle='--')
            ax1.legend(fontsize=11, loc='upper left')
            ax1.yaxis.set_major_locator(MaxNLocator(integer=True))
            
            # 두 번째 그래프: 시간대별 쾌적도 변화
            ax2.plot(times, comfort_indices, marker='D', linewidth=2.5, markersize=6, label='쾌적도 지수', color='#9B59B6')
            ax2.fill_between(times, comfort_indices, alpha=0.3, color='#9B59B6')
            
            # 쾌적도 등급별 배경색 영역 추가
            ax2.axhspan(80, 100, alpha=0.15, color='#2ecc71', label='최고 (80~100)')
            ax2.axhspan(60, 80, alpha=0.15, color='#f39c12', label='좋음 (60~80)')
            ax2.axhspan(40, 60, alpha=0.15, color='#e74c3c', label='보통 (40~60)')
            ax2.axhspan(0, 40, alpha=0.15, color='#c0392b', label='나쁨 (0~40)')
            
            # 두 번째 그래프 스타일 설정
            ax2.set_xlabel('시간', fontsize=12, fontweight='bold')
            ax2.set_ylabel('쾌적도 지수 (점)', fontsize=12, fontweight='bold')
            ax2.set_title(f'{selected_city} - 시간대별 쾌적도 변화', fontsize=14, fontweight='bold', pad=20)
            ax2.set_ylim(0, 100)
            ax2.grid(True, alpha=0.3, linestyle='--')
            ax2.legend(fontsize=10, loc='upper right')
            ax2.yaxis.set_major_locator(MaxNLocator(integer=True))
            
            # X축 시간 포맷 설정 (두 그래프 모두)
            for ax in [ax1, ax2]:
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
                ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
            
            plt.xticks(rotation=45, ha='right')
            
            # 레이아웃 자동 조정
            plt.tight_layout()
            
            # Streamlit에 차트 표시
            st.pyplot(fig)
            
        except Exception as e:
            st.warning("⚠️ 시간대별 기온 차트를 불러올 수 없습니다. 잠시 후 다시 시도해주세요.")
        # ==================== 동적 차트 구현 종료 ====================
        
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            st.error("❌ API 키가 유효하지 않습니다. OpenWeatherMap API 키를 확인해주세요.")
        elif response.status_code == 404:
            st.error("❌ 해당 도시를 찾을 수 없습니다.")
        else:
            st.error(f"❌ API 오류: {response.status_code}")
    except requests.exceptions.RequestException:
        st.error("❌ OpenWeatherMap API에 연결할 수 없습니다. 인터넷 연결을 확인해주세요.")
    except KeyError:
        st.error("❌ API 응답 형식이 예상과 다릅니다.")

else:
    st.info("👈 시작하려면 사이드바에 OpenWeatherMap API 키를 입력해주세요!")
    st.markdown("""
    ### 🚀 시작하기:
    1. [OpenWeatherMap](https://openweathermap.org/api)에 방문하세요
    2. 무료 계정으로 가입하세요
    3. API 키를 생성하세요
    4. 생성한 API 키를 사이드바에 입력하세요
    5. 실시간 날씨 정보를 확인하세요! 🌤️
    """)
