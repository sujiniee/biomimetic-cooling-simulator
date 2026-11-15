import streamlit as st
import pandas as pd
import numpy as np

# ============================================================
# 생체모방 냉각 환경 시뮬레이터
# 사용자의 Colab 노트북 핵심 계산 로직을 Streamlit 앱으로 옮김
# ============================================================

st.set_page_config(
    page_title="생체모방 냉각 환경 시뮬레이터",
    page_icon="🌿",
    layout="wide"
)

LATENT_HEAT = 2.45  # MJ/kg (20°C 기준)

def calculate_latent_heat(et_rate):
    """
    et_rate: 증발산량 (mm/day)
    반환값: 단위 면적당 잠열 흡수량 (MJ/m²/day, kWh/m²/day)
    """
    energy_mj = et_rate * LATENT_HEAT
    energy_kwh = energy_mj / 3.6
    return energy_mj, energy_kwh

et_scenarios = {
    "낮음": 0.5,
    "중간": 2.5,
    "높음": 4.9
}

st.title("생체모방 냉각 환경 시뮬레이터")
st.caption("Model 1 | 식물의 증산 작용에 따른 잠열 흡수량 시나리오 분석")
st.write(
    "실제 데이터센터 외부 온도 자료를 환경 조건으로 표시하고, "
    "문헌 기반 증발산 시나리오와 식생 면적에 따른 잠열 흡수량을 계산합니다."
)

with st.expander("사용 방법 및 데이터 안내", expanded=True):
    st.markdown(
        """
        1. Fraunhofer BodenType Data Center One의 원본 Excel 파일을 업로드합니다.
        2. 외부 온도 구간, 증발산 시나리오, 식생 면적을 선택합니다.
        3. 계산 결과와 시나리오 비교 그래프를 확인합니다.

        **분석 데이터:** `Humidity POD1` 시트의 시간(0열), 외부 온도(1열), 외부 비습 원자료(2열)를 사용합니다.
        원본 노트북과 동일하게 5행부터 8740행까지의 8,736개 관측값을 추출합니다.
        """
    )

uploaded_file = st.file_uploader(
    "원본 데이터 파일 업로드 (.xlsx)",
    type=["xlsx"],
    help="Fraunhofer BodenType Data Center One의 Data-Collation-version2.xlsx 파일"
)

if uploaded_file is None:
    st.info("시뮬레이터를 시작하려면 원본 Excel 파일을 업로드하세요.")
    st.stop()

try:
    humidity_df = pd.read_excel(
        uploaded_file,
        sheet_name="Humidity POD1",
        header=None,
        engine="openpyxl"
    )

    # Colab 노트북의 STEP 11과 동일한 열 및 행 범위 사용
    environment_df = pd.DataFrame({
        "시간": pd.to_datetime(humidity_df.iloc[5:8741, 0], errors="coerce"),
        "외부온도_C": pd.to_numeric(
            humidity_df.iloc[5:8741, 1], errors="coerce"
        ),
        "외부비습_raw": pd.to_numeric(
            humidity_df.iloc[5:8741, 2], errors="coerce"
        )
    })

    environment_df = environment_df.dropna(subset=["시간", "외부온도_C"]).copy()

    if environment_df.empty:
        st.error("외부 온도 데이터가 없습니다. 올바른 원본 Excel 파일인지 확인하세요.")
        st.stop()

    # Colab 노트북의 STEP 23과 동일한 분위수 기준
    lower_temp = environment_df["외부온도_C"].quantile(0.10)
    upper_temp = environment_df["외부온도_C"].quantile(0.90)

    def classify_temperature(temp):
        if temp <= lower_temp:
            return "저온"
        elif temp >= upper_temp:
            return "고온"
        else:
            return "일반"

    environment_df["온도_구간"] = (
        environment_df["외부온도_C"].apply(classify_temperature)
    )

    # Colab 노트북의 STEP 24와 동일한 통계
    temperature_stats = (
        environment_df.groupby("온도_구간")["외부온도_C"]
        .agg(["count", "mean", "min", "max"])
        .reindex(["저온", "일반", "고온"])
        .reset_index()
    )

    temperature_stats.columns = [
        "온도 구간",
        "측정 시간",
        "평균 온도_C",
        "최저 온도_C",
        "최고 온도_C"
    ]

except Exception as exc:
    st.error(f"파일을 읽는 중 문제가 발생했습니다: {exc}")
    st.stop()

st.success(
    f"데이터를 불러왔습니다: {len(environment_df):,}개 관측값 "
    f"({environment_df['시간'].min():%Y-%m-%d} ~ {environment_df['시간'].max():%Y-%m-%d})"
)

st.subheader("1. 시뮬레이션 조건")

left, middle, right = st.columns(3)

with left:
    selected_temp = st.selectbox(
        "외부 온도 환경 구간",
        ["저온", "일반", "고온"],
        index=1
    )

with middle:
    selected_scenario = st.selectbox(
        "증발산 시나리오",
        ["낮음", "중간", "높음"],
        index=1
    )

with right:
    vegetation_area = st.slider(
        "식생 적용 면적 (m²)",
        min_value=1,
        max_value=1000,
        value=100,
        step=1
    )

selected_temp_row = temperature_stats.loc[
    temperature_stats["온도 구간"] == selected_temp
]

if selected_temp_row.empty:
    st.error("선택한 온도 구간의 통계값을 계산할 수 없습니다.")
    st.stop()

mean_temp = float(selected_temp_row["평균 온도_C"].iloc[0])
et = et_scenarios[selected_scenario]

# Colab 노트북의 STEP 18, STEP 27과 동일한 핵심 계산
energy_mj, energy_kwh = calculate_latent_heat(et)
total_mj = energy_mj * vegetation_area
total_kwh = energy_kwh * vegetation_area

st.subheader("2. 시뮬레이션 결과")

m1, m2, m3, m4 = st.columns(4)
m1.metric("평균 외부 온도", f"{mean_temp:.2f} °C")
m2.metric("증발산량", f"{et:.2f} mm/day")
m3.metric("단위 면적당 잠열 흡수량", f"{energy_kwh:.3f} kWh/m²/day")
m4.metric("전체 잠열 흡수량", f"{total_kwh:,.2f} kWh/day")

st.metric("전체 잠열 흡수량 (MJ/day)", f"{total_mj:,.2f} MJ/day")

st.subheader("3. 증발산 시나리오 비교")

comparison_rows = []
for scenario_name, scenario_et in et_scenarios.items():
    scenario_mj, scenario_kwh = calculate_latent_heat(scenario_et)
    comparison_rows.append({
        "시나리오": scenario_name,
        "증발산량 (mm/day)": scenario_et,
        "전체 잠열 흡수량 (kWh/day)": scenario_kwh * vegetation_area
    })

comparison_df = pd.DataFrame(comparison_rows).set_index("시나리오")
st.bar_chart(comparison_df[["전체 잠열 흡수량 (kWh/day)"]])

st.dataframe(
    comparison_df.reset_index().round(3),
    use_container_width=True,
    hide_index=True
)

st.subheader("4. 실제 데이터의 온도 구간 통계")
st.dataframe(temperature_stats.round(2), use_container_width=True, hide_index=True)
st.caption(
    f"저온 기준: {lower_temp:.2f} °C 이하 | "
    f"고온 기준: {upper_temp:.2f} °C 이상"
)

with st.expander("계산 원리와 모델의 한계"):
    st.latex(r"Q_{latent}=ET\\times 2.45")
    st.markdown(
        """
        - 증발산량(ET): mm/day
        - 잠열 흡수량: MJ/m²/day
        - kWh 환산: MJ ÷ 3.6
        - 전체 잠열 흡수량: 단위 면적당 잠열 흡수량 × 식생 면적

        **주의:** 결과는 증발산에 따른 잠열 흡수 에너지의 추정치입니다.
        실제 데이터센터 공기 온도 하강량이나 전력 절감량을 직접 의미하지 않습니다.
        증발산량 0.5, 2.5, 4.9 mm/day는 문헌 기반 시나리오 가정값이며,
        해당 데이터센터에서 직접 측정한 값이 아닙니다.
        온도 구간은 환경 조건을 표시하기 위한 것이며, 현재 모델은 온도에 따라
        증발산량이 자동으로 변한다고 가정하지 않습니다.
        """
    )

st.caption(
    "연구용 시뮬레이터 | 원본 Colab 노트북의 데이터 추출 범위, "
    "온도 분위수 분류, 잠열 계산식을 바탕으로 구현"
)
