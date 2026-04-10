"""
合成数据生成器
生成模拟的医疗检验数据（患者、检验结果、仪器、参考范围）
"""

import csv
import json
import os
import random
from datetime import datetime, timedelta

random.seed(42)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "sample_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ──────────────────────────────────────────────────────────────
# 数据素材
# ──────────────────────────────────────────────────────────────
FAMILY_NAMES = [
    "张", "王", "李", "赵", "刘", "陈", "杨", "黄", "周", "吴",
    "徐", "孙", "马", "朱", "胡", "郭", "林", "何", "高", "罗",
    "郑", "梁", "谢", "宋", "唐", "韩", "冯", "董", "萧", "程",
    "曹", "袁", "邓", "许", "傅", "沈", "曾", "彭", "吕", "苏",
    "卢", "蒋", "蔡", "贾", "丁", "魏", "薛", "叶", "阎", "余",
    "潘", "杜", "戴", "夏", "钟", "汪", "田", "任", "姜", "范",
    "方", "石", "姚", "谭", "廖", "邹", "熊", "金", "陆", "郝",
    "孔", "白", "崔", "康", "毛", "邱", "秦", "江", "史", "顾",
]

GIVEN_NAMES_MALE = [
    "伟", "强", "磊", "洋", "勇", "军", "杰", "涛", "明", "超",
    "亮", "辉", "鹏", "飞", "刚", "华", "建", "文", "斌", "博",
    "浩", "宇", "泽", "翔", "龙", "峰", "海", "波", "鑫", "健",
    "志", "俊", "晨", "恒", "毅", "轩", "睿", "天", "嘉", "凯",
]

GIVEN_NAMES_FEMALE = [
    "芳", "娟", "敏", "静", "丽", "燕", "霞", "秀", "玲", "桂",
    "英", "华", "慧", "萍", "红", "云", "莉", "荣", "梅", "兰",
    "婷", "雪", "琳", "颖", "佳", "倩", "欣", "怡", "瑶", "璐",
    "洁", "蕊", "薇", "琪", "悦", "雯", "妍", "晴", "梦", "彤",
]

DEPARTMENTS = [
    "内科", "外科", "急诊科", "妇产科", "儿科", "骨科",
    "心内科", "呼吸内科", "消化内科", "神经内科", "内分泌科",
    "肾内科", "血液科", "肿瘤科", "泌尿外科", "普外科",
    "ICU", "新生儿科", "眼科", "耳鼻喉科", "皮肤科",
    "口腔科", "中医科", "康复科", "老年科", "感染科",
]

DIAGNOSES = [
    "高血压", "2型糖尿病", "冠心病", "急性上呼吸道感染",
    "肺炎", "慢性支气管炎", "胃炎", "消化性溃疡",
    "肝功能异常", "肾功能不全", "贫血", "甲状腺功能亢进",
    "甲状腺功能减退", "类风湿关节炎", "骨折", "脑梗死",
    "心力衰竭", "房颤", "慢性肾病", "肝硬化",
    "胆囊炎", "阑尾炎", "尿路感染", "带状疱疹",
    "支气管哮喘", "慢性阻塞性肺病", "痛风", "高脂血症",
    "健康体检", "术前检查", "产检", "复查",
]

# 检验项目及其合理范围
TEST_ITEMS = {
    "WBC":  {"name": "白细胞计数",   "unit": "10^9/L", "low": 3.5,  "high": 9.5,  "mean": 6.5,   "std": 1.8},
    "RBC":  {"name": "红细胞计数",   "unit": "10^12/L","low": 3.8,  "high": 5.8,  "mean": 4.5,   "std": 0.5},
    "HGB":  {"name": "血红蛋白",     "unit": "g/L",    "low": 115,  "high": 175,  "mean": 140,   "std": 15},
    "PLT":  {"name": "血小板计数",   "unit": "10^9/L", "low": 125,  "high": 350,  "mean": 220,   "std": 50},
    "ALT":  {"name": "丙氨酸氨基转移酶","unit": "U/L", "low": 7,    "high": 56,   "mean": 25,    "std": 12},
    "AST":  {"name": "天冬氨酸氨基转移酶","unit":"U/L","low": 10,   "high": 40,   "mean": 22,    "std": 8},
    "TBIL": {"name": "总胆红素",     "unit": "umol/L", "low": 3.4,  "high": 20.5, "mean": 10,    "std": 4},
    "DBIL": {"name": "直接胆红素",   "unit": "umol/L", "low": 0,    "high": 6.8,  "mean": 3.0,   "std": 1.5},
    "TP":   {"name": "总蛋白",       "unit": "g/L",    "low": 65,   "high": 85,   "mean": 72,    "std": 5},
    "ALB":  {"name": "白蛋白",       "unit": "g/L",    "low": 40,   "high": 55,   "mean": 45,    "std": 4},
    "BUN":  {"name": "尿素氮",       "unit": "mmol/L", "low": 2.6,  "high": 7.5,  "mean": 5.0,   "std": 1.2},
    "CR":   {"name": "肌酐",         "unit": "umol/L", "low": 44,   "high": 133,  "mean": 75,    "std": 20},
    "UA":   {"name": "尿酸",         "unit": "umol/L", "low": 150,  "high": 416,  "mean": 300,   "std": 60},
    "GLU":  {"name": "葡萄糖",       "unit": "mmol/L", "low": 3.9,  "high": 6.1,  "mean": 5.2,   "std": 0.8},
    "TC":   {"name": "总胆固醇",     "unit": "mmol/L", "low": 2.8,  "high": 5.2,  "mean": 4.2,   "std": 0.8},
    "TG":   {"name": "甘油三酯",     "unit": "mmol/L", "low": 0.56, "high": 1.7,  "mean": 1.2,   "std": 0.5},
    "K":    {"name": "钾",           "unit": "mmol/L", "low": 3.5,  "high": 5.3,  "mean": 4.2,   "std": 0.4},
    "Na":   {"name": "钠",           "unit": "mmol/L", "low": 137,  "high": 147,  "mean": 141,   "std": 2.5},
    "Cl":   {"name": "氯",           "unit": "mmol/L", "low": 99,   "high": 110,  "mean": 104,   "std": 3},
    "Ca":   {"name": "钙",           "unit": "mmol/L", "low": 2.11, "high": 2.52, "mean": 2.3,   "std": 0.1},
}

INSTRUMENT_MODELS = [
    ("BC-6800Plus", "迈瑞", "血液分析仪"),
    ("BC-6800",     "迈瑞", "血液分析仪"),
    ("XN-9000",     "希森美康", "血液分析仪"),
    ("XN-3000",     "希森美康", "血液分析仪"),
    ("AU5800",      "贝克曼", "生化分析仪"),
    ("AU5812",      "贝克曼", "生化分析仪"),
    ("Cobas8000",   "罗氏", "生化分析仪"),
    ("Cobas6000",   "罗氏", "生化分析仪"),
    ("Vitros5600",  "强生", "生化分析仪"),
    ("ADVIA2400",   "西门子", "生化分析仪"),
]

PROVINCE_CODES = [
    "110", "120", "130", "140", "150", "210", "220", "230",
    "310", "320", "330", "340", "350", "360", "370", "410",
    "420", "430", "440", "450", "500", "510", "520", "530",
    "610", "620", "630", "640", "650",
]


def generate_id_card(birth_year: int, birth_month: int,
                     birth_day: int, gender: str) -> str:
    """生成模拟身份证号"""
    province = random.choice(PROVINCE_CODES)
    city = f"{random.randint(1, 20):02d}"
    county = f"{random.randint(1, 30):02d}"
    seq = random.randint(0, 99)
    gender_digit = random.choice([1, 3, 5, 7, 9]) if gender == "male" else random.choice([0, 2, 4, 6, 8])
    id17 = f"{province}{city}{county}{birth_year:04d}{birth_month:02d}{birth_day:02d}{seq:02d}{gender_digit}"

    # 校验码计算
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check_chars = "10X98765432"
    total = sum(int(id17[i]) * weights[i] for i in range(17))
    check = check_chars[total % 11]
    return id17 + check


def generate_patients(count: int = 2000) -> list:
    """生成患者数据"""
    patients = []
    used_ids = set()

    for i in range(count):
        patient_id = f"P{100000 + i}"

        gender = random.choice(["male", "female"])
        family = random.choice(FAMILY_NAMES)
        if gender == "male":
            given = random.choice(GIVEN_NAMES_MALE)
            if random.random() < 0.4:
                given += random.choice(GIVEN_NAMES_MALE)
        else:
            given = random.choice(GIVEN_NAMES_FEMALE)
            if random.random() < 0.4:
                given += random.choice(GIVEN_NAMES_FEMALE)
        name = family + given

        # 年龄分布：偏向中老年（模拟医院真实分布）
        age_dist = random.random()
        if age_dist < 0.05:
            age = random.randint(0, 5)
        elif age_dist < 0.10:
            age = random.randint(6, 17)
        elif age_dist < 0.35:
            age = random.randint(18, 40)
        elif age_dist < 0.70:
            age = random.randint(41, 65)
        else:
            age = random.randint(66, 95)

        birth_year = 2024 - age
        birth_month = random.randint(1, 12)
        birth_day = random.randint(1, 28)

        id_card = generate_id_card(birth_year, birth_month, birth_day, gender)
        while id_card in used_ids:
            id_card = generate_id_card(birth_year, birth_month, birth_day, gender)
        used_ids.add(id_card)

        department = random.choice(DEPARTMENTS)
        # 多个诊断的可能
        n_diag = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
        diagnosis = "; ".join(random.sample(DIAGNOSES, n_diag))

        patients.append({
            "patient_id": patient_id,
            "name": name,
            "id_card": id_card,
            "gender": gender,
            "age": age,
            "department": department,
            "diagnosis": diagnosis,
        })

    return patients


def generate_lab_results(patients: list, count: int = 8000) -> list:
    """生成检验结果"""
    results = []
    test_codes = list(TEST_ITEMS.keys())
    instrument_ids = [f"INS-{i+1:03d}" for i in range(50)]

    # 每个仪器对应的检验项目类型
    hematology_instruments = instrument_ids[:20]
    biochemistry_instruments = instrument_ids[20:]
    hematology_tests = ["WBC", "RBC", "HGB", "PLT"]
    biochemistry_tests = [t for t in test_codes if t not in hematology_tests]

    base_date = datetime(2024, 1, 1)

    for i in range(count):
        patient = random.choice(patients)
        result_id = f"R{1000000 + i}"

        # 选择检验项目
        test_code = random.choice(test_codes)
        test_info = TEST_ITEMS[test_code]

        # 匹配仪器
        if test_code in hematology_tests:
            instrument_id = random.choice(hematology_instruments)
        else:
            instrument_id = random.choice(biochemistry_instruments)

        # 生成合理的检验值（正态分布 + 少量异常值）
        if random.random() < 0.05:
            # 5%的异常值
            value = random.uniform(
                test_info["mean"] - 4 * test_info["std"],
                test_info["mean"] + 4 * test_info["std"],
            )
        else:
            value = random.gauss(test_info["mean"], test_info["std"])

        # 确保值在合理范围内（不小于0，对于大多数检验项目）
        if test_code not in []:
            value = max(0.01, value)

        value = round(value, 2)

        # 判断异常标志
        if value < test_info["low"]:
            flag = "L"
        elif value > test_info["high"]:
            flag = "H"
        else:
            flag = "N"

        # 随机日期（2024年全年）
        days_offset = random.randint(0, 364)
        hours_offset = random.randint(6, 22)
        minutes_offset = random.randint(0, 59)
        test_date = base_date + timedelta(
            days=days_offset, hours=hours_offset, minutes=minutes_offset
        )

        results.append({
            "result_id": result_id,
            "patient_id": patient["patient_id"],
            "test_code": test_code,
            "test_name": test_info["name"],
            "value": value,
            "unit": test_info["unit"],
            "instrument_id": instrument_id,
            "test_date": test_date.strftime("%Y-%m-%d %H:%M:%S"),
            "flag": flag,
        })

    # 按日期排序
    results.sort(key=lambda r: r["test_date"])
    return results


def generate_instruments(count: int = 50) -> list:
    """生成仪器数据"""
    instruments = []
    locations = ["检验科A区", "检验科B区", "检验科C区",
                 "急诊检验", "门诊检验"]
    base_date = datetime(2024, 1, 1)

    for i in range(count):
        instrument_id = f"INS-{i+1:03d}"
        model_info = INSTRUMENT_MODELS[i % len(INSTRUMENT_MODELS)]

        # 前20台是血液分析仪，后30台是生化分析仪
        if i < 20:
            supported_tests = "WBC,RBC,HGB,PLT"
        else:
            supported_tests = "ALT,AST,TBIL,DBIL,TP,ALB,BUN,CR,UA,GLU,TC,TG,K,Na,Cl,Ca"

        last_cal = base_date + timedelta(days=random.randint(0, 300))
        next_cal = last_cal + timedelta(days=random.randint(30, 90))

        instruments.append({
            "instrument_id": instrument_id,
            "name": f"{model_info[0]}-{i+1:02d}",
            "manufacturer": model_info[1],
            "model": model_info[0],
            "serial_number": f"SN{random.randint(100000, 999999)}",
            "department": "检验科",
            "location": random.choice(locations),
            "status": random.choices(
                ["online", "offline", "maintenance"],
                weights=[0.85, 0.05, 0.10]
            )[0],
            "last_calibration": last_cal.strftime("%Y-%m-%d"),
            "next_calibration": next_cal.strftime("%Y-%m-%d"),
            "supported_tests": supported_tests,
            "daily_capacity": random.randint(100, 1000),
        })

    return instruments


def generate_reference_ranges() -> dict:
    """生成参考范围JSON"""
    ranges = {}
    for code, info in TEST_ITEMS.items():
        ranges[code] = {
            "test_code": code,
            "test_name": info["name"],
            "unit": info["unit"],
            "ranges": [
                {
                    "population": "成人（通用）",
                    "gender": None,
                    "age_min": 18,
                    "age_max": 120,
                    "lower_limit": info["low"],
                    "upper_limit": info["high"],
                },
                {
                    "population": "成年男性",
                    "gender": "male",
                    "age_min": 18,
                    "age_max": 120,
                    "lower_limit": round(info["low"] * (1.05 if code in ["RBC", "HGB", "CR"] else 1.0), 2),
                    "upper_limit": round(info["high"] * (1.05 if code in ["RBC", "HGB", "CR"] else 1.0), 2),
                },
                {
                    "population": "成年女性",
                    "gender": "female",
                    "age_min": 18,
                    "age_max": 120,
                    "lower_limit": round(info["low"] * (0.95 if code in ["RBC", "HGB", "CR"] else 1.0), 2),
                    "upper_limit": round(info["high"] * (0.95 if code in ["RBC", "HGB", "CR"] else 1.0), 2),
                },
                {
                    "population": "儿童",
                    "gender": None,
                    "age_min": 0,
                    "age_max": 17,
                    "lower_limit": round(info["low"] * 0.9, 2),
                    "upper_limit": round(info["high"] * 0.95, 2),
                },
            ],
        }
    return ranges


def main():
    print("正在生成合成数据...")

    # 1. 患者数据
    print("  生成患者数据 (2000条)...")
    patients = generate_patients(2000)
    patients_path = os.path.join(OUTPUT_DIR, "patients.csv")
    with open(patients_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "patient_id", "name", "id_card", "gender", "age",
            "department", "diagnosis",
        ])
        writer.writeheader()
        writer.writerows(patients)
    print(f"    -> {patients_path} ({len(patients)}条)")

    # 2. 检验结果
    print("  生成检验结果 (8000条)...")
    results = generate_lab_results(patients, 8000)
    results_path = os.path.join(OUTPUT_DIR, "lab_results.csv")
    with open(results_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "result_id", "patient_id", "test_code", "test_name",
            "value", "unit", "instrument_id", "test_date", "flag",
        ])
        writer.writeheader()
        writer.writerows(results)
    print(f"    -> {results_path} ({len(results)}条)")

    # 3. 仪器数据
    print("  生成仪器数据 (50条)...")
    instruments = generate_instruments(50)
    instruments_path = os.path.join(OUTPUT_DIR, "instruments.csv")
    with open(instruments_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "instrument_id", "name", "manufacturer", "model",
            "serial_number", "department", "location", "status",
            "last_calibration", "next_calibration",
            "supported_tests", "daily_capacity",
        ])
        writer.writeheader()
        writer.writerows(instruments)
    print(f"    -> {instruments_path} ({len(instruments)}条)")

    # 4. 参考范围
    print("  生成参考范围...")
    ref_ranges = generate_reference_ranges()
    ref_path = os.path.join(OUTPUT_DIR, "reference_ranges.json")
    with open(ref_path, "w", encoding="utf-8") as f:
        json.dump(ref_ranges, f, ensure_ascii=False, indent=2)
    print(f"    -> {ref_path}")

    print("\n数据生成完成!")
    print(f"  患者: {len(patients)}条")
    print(f"  检验结果: {len(results)}条")
    print(f"  仪器: {len(instruments)}条")
    print(f"  参考范围: {len(ref_ranges)}项")


if __name__ == "__main__":
    main()
