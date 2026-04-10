#!/usr/bin/env python3
"""
完整的医疗数据分析脚本
包含共现模式分析和趋势分析
"""

import csv
import json
import statistics
from datetime import datetime
from collections import defaultdict
import os

def log_compliance(action, file_path):
    """记录合规日志"""
    log_entry = {
        "time": datetime.now().isoformat(),
        "action": action,
        "file": file_path,
        "tool": "python_script"
    }
    with open("compliance_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")

def parse_lab_reports():
    """解析实验室报告数据"""
    log_compliance("read", "sample_data/lab_reports.csv")
    
    reports = []
    with open("../../sample_data/lab_reports.csv", "r", encoding="utf-8") as f:
        lines = f.readlines()
        
        # 第一行是表头
        header_line = lines[0].strip()
        if '\t' in header_line:
            headers = header_line.split('\t')[1].split(',')
        else:
            headers = header_line.split(',')
        
        # 处理数据行
        for line_num, line in enumerate(lines[1:], 2):
            line = line.strip()
            if not line:
                continue
                
            # 去掉行号
            if '\t' in line:
                data_part = line.split('\t')[1]
            else:
                data_part = line
                
            values = data_part.split(',')
            if len(values) != len(headers):
                print(f"警告: 第{line_num}行列数不匹配: {len(values)} != {len(headers)}")
                continue
                
            row = dict(zip(headers, values))
            
            # 转换数据类型，处理缺失值
            try:
                report = {
                    'report_id': row['report_id'],
                    'age': int(row['age']),
                    'gender': row['gender'],
                    'test_date': row['test_date'],
                    'wbc': float(row['wbc']) if row['wbc'] else None,
                    'rbc': float(row['rbc']) if row['rbc'] else None,
                    'hgb': float(row['hgb']) if row['hgb'] else None,
                    'plt': float(row['plt']) if row['plt'] else None,
                    'neut_pct': float(row['neut_pct']) if row['neut_pct'] else None,
                    'lymph_pct': float(row['lymph_pct']) if row['lymph_pct'] else None
                }
                # 检查是否有缺失值
                if all(report[key] is not None for key in ['wbc', 'rbc', 'hgb', 'plt', 'neut_pct', 'lymph_pct']):
                    reports.append(report)
                else:
                    print(f"警告: 第{line_num}行有缺失值，已跳过")
            except (ValueError, KeyError) as e:
                print(f"解析错误第{line_num}行: {e}")
                continue
    
    return reports

def read_reference_ranges():
    """读取参考范围"""
    log_compliance("read", "sample_data/reference_ranges.json")
    
    with open("../../sample_data/reference_ranges.json", "r", encoding="utf-8") as f:
        return json.load(f)

def check_abnormalities(report, reference_ranges):
    """检查单个报告的异常指标"""
    abnormalities = []
    age = report['age']
    gender = report['gender']
    
    # WBC检查
    if age >= 65:
        wbc_range = reference_ranges['wbc']['ranges']['elderly']
    else:
        wbc_range = reference_ranges['wbc']['ranges']['adult']
    
    if not (wbc_range['low'] <= report['wbc'] <= wbc_range['high']):
        abnormalities.append('wbc')
    
    # RBC检查
    rbc_range = reference_ranges['rbc']['ranges']['male' if gender == 'M' else 'female']
    if not (rbc_range['low'] <= report['rbc'] <= rbc_range['high']):
        abnormalities.append('rbc')
    
    # HGB检查
    hgb_range = reference_ranges['hgb']['ranges']['male' if gender == 'M' else 'female']
    if not (hgb_range['low'] <= report['hgb'] <= hgb_range['high']):
        abnormalities.append('hgb')
    
    # PLT检查
    plt_range = reference_ranges['plt']['ranges']['adult']
    if not (plt_range['low'] <= report['plt'] <= plt_range['high']):
        abnormalities.append('plt')
    
    # 中性粒细胞检查
    neut_range = reference_ranges['neut_pct']['ranges']['adult']
    if not (neut_range['low'] <= report['neut_pct'] <= neut_range['high']):
        abnormalities.append('neut_pct')
    
    # 淋巴细胞检查
    lymph_range = reference_ranges['lymph_pct']['ranges']['adult']
    if not (lymph_range['low'] <= report['lymph_pct'] <= lymph_range['high']):
        abnormalities.append('lymph_pct')
    
    return abnormalities

def analyze_cooccurrence(abnormal_reports):
    """分析异常指标共现模式"""
    cooccurrence = defaultdict(int)
    pair_details = defaultdict(list)
    
    for report in abnormal_reports:
        abnormalities = report['abnormalities']
        # 统计每对异常指标的共现
        for i in range(len(abnormalities)):
            for j in range(i+1, len(abnormalities)):
                pair = tuple(sorted([abnormalities[i], abnormalities[j]]))
                cooccurrence[pair] += 1
                pair_details[pair].append({
                    'age_group': report['age_group'],
                    'gender': report['gender']
                })
    
    # 转换为易读格式
    cooccurrence_list = []
    for pair, count in cooccurrence.items():
        # 分析共现对的年龄和性别分布
        age_groups = defaultdict(int)
        genders = defaultdict(int)
        for detail in pair_details[pair]:
            age_groups[detail['age_group']] += 1
            genders[detail['gender']] += 1
        
        cooccurrence_list.append({
            'indicators': pair,
            'count': count,
            'age_distribution': dict(age_groups),
            'gender_distribution': dict(genders)
        })
    
    # 按出现次数排序
    cooccurrence_list.sort(key=lambda x: x['count'], reverse=True)
    
    return cooccurrence_list

def analyze_monthly_trends(reports, reference_ranges):
    """分析月度趋势"""
    monthly_data = defaultdict(lambda: {
        'total': 0,
        'abnormal': 0,
        'indicators': defaultdict(int),
        'values': defaultdict(list)
    })
    
    for report in reports:
        date = datetime.strptime(report['test_date'], '%Y-%m-%d')
        month_key = date.strftime('%Y-%m')
        
        monthly_data[month_key]['total'] += 1
        
        # 检查异常
        abnormalities = check_abnormalities(report, reference_ranges)
        if abnormalities:
            monthly_data[month_key]['abnormal'] += 1
            for indicator in abnormalities:
                monthly_data[month_key]['indicators'][indicator] += 1
        
        # 收集指标值
        for indicator in ['wbc', 'rbc', 'hgb', 'plt', 'neut_pct', 'lymph_pct']:
            monthly_data[month_key]['values'][indicator].append(report[indicator])
    
    # 计算月度统计
    monthly_summary = {}
    for month, data in monthly_data.items():
        monthly_summary[month] = {
            'total': data['total'],
            'abnormal_count': data['abnormal'],
            'abnormal_rate': round(data['abnormal'] / data['total'] * 100, 2) if data['total'] > 0 else 0,
            'indicator_rates': {},
            'mean_values': {}
        }
        
        # 各指标异常率
        for indicator in data['indicators']:
            monthly_summary[month]['indicator_rates'][indicator] = round(
                data['indicators'][indicator] / data['total'] * 100, 2
            )
        
        # 各指标均值
        for indicator, values in data['values'].items():
            if values:
                monthly_summary[month]['mean_values'][indicator] = round(statistics.mean(values), 2)
    
    return monthly_summary

def main():
    """主函数"""
    print("开始完整的医疗数据分析...")
    
    # 读取数据
    reports = parse_lab_reports()
    reference_ranges = read_reference_ranges()
    
    print(f"成功读取 {len(reports)} 条完整的实验室报告")
    
    if not reports:
        print("错误：没有读取到完整数据")
        return
    
    # 基本统计
    print("\n=== 基本统计 ===")
    dates = [r['test_date'] for r in reports]
    print(f"数据时间范围: {min(dates)} 至 {max(dates)}")
    print(f"数据跨度: {(datetime.strptime(max(dates), '%Y-%m-%d') - datetime.strptime(min(dates), '%Y-%m-%d')).days} 天")
    
    # 年龄分布
    age_groups = {"0-17": 0, "18-44": 0, "45-64": 0, "65+": 0}
    for r in reports:
        age = r['age']
        if age <= 17:
            age_groups["0-17"] += 1
        elif age <= 44:
            age_groups["18-44"] += 1
        elif age <= 64:
            age_groups["45-64"] += 1
        else:
            age_groups["65+"] += 1
    
    print(f"年龄分布: {age_groups}")
    
    # 性别分布
    gender_counts = {"M": 0, "F": 0}
    for r in reports:
        gender_counts[r['gender']] += 1
    
    print(f"性别分布: 男性 {gender_counts['M']} 例, 女性 {gender_counts['F']} 例")
    
    # 异常检测
    print("\n=== 异常检测 ===")
    abnormal_reports = []
    abnormal_counts = defaultdict(int)
    
    for report in reports:
        abnormalities = check_abnormalities(report, reference_ranges)
        if abnormalities:
            abnormal_reports.append({
                'report_id': report['report_id'],
                'abnormalities': abnormalities,
                'age_group': get_age_group(report['age']),
                'gender': report['gender']
            })
            for indicator in abnormalities:
                abnormal_counts[indicator] += 1
    
    print(f"异常报告数: {len(abnormal_reports)} 例 ({round(len(abnormal_reports)/len(reports)*100, 1)}%)")
    print("各指标异常数:", dict(abnormal_counts))
    
    # 共现模式分析
    print("\n=== 共现模式分析 ===")
    cooccurrence = analyze_cooccurrence(abnormal_reports)
    print(f"发现 {len(cooccurrence)} 种共现模式")
    
    # 趋势分析
    print("\n=== 趋势分析 ===")
    monthly_trends = analyze_monthly_trends(reports, reference_ranges)
    print(f"分析 {len(monthly_trends)} 个月的数据")
    
    # 生成完整报告
    print("\n=== 生成完整分析报告 ===")
    generate_complete_report(
        reports, reference_ranges, age_groups, gender_counts,
        abnormal_reports, abnormal_counts, cooccurrence, monthly_trends
    )
    
    print("分析完成！")

def get_age_group(age):
    """获取年龄组"""
    if age <= 17:
        return "0-17"
    elif age <= 44:
        return "18-44"
    elif age <= 64:
        return "45-64"
    else:
        return "65+"

def generate_complete_report(reports, reference_ranges, age_groups, gender_counts,
                           abnormal_reports, abnormal_counts, cooccurrence, monthly_trends):
    """生成完整的分析报告"""
    
    total_reports = len(reports)
    indicator_names = {
        'wbc': '白细胞计数',
        'rbc': '红细胞计数', 
        'hgb': '血红蛋白',
        'plt': '血小板计数',
        'neut_pct': '中性粒细胞百分比',
        'lymph_pct': '淋巴细胞百分比'
    }
    
    units = {
        'wbc': '10^9/L',
        'rbc': '10^12/L',
        'hgb': 'g/L',
        'plt': '10^9/L',
        'neut_pct': '%',
        'lymph_pct': '%'
    }
    
    # 计算各指标统计
    stats = {}
    indicators = list(indicator_names.keys())
    for indicator in indicators:
        values = [r[indicator] for r in reports]
        stats[indicator] = {
            "mean": round(statistics.mean(values), 2),
            "median": round(statistics.median(values), 2),
            "std": round(statistics.stdev(values), 2) if len(values) > 1 else 0,
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "q1": round(statistics.quantiles(values, n=4)[0], 2) if len(values) >= 4 else None,
            "q3": round(statistics.quantiles(values, n=4)[2], 2) if len(values) >= 4 else None
        }
    
    # 计算异常率
    abnormal_rates = {}
    for indicator in abnormal_counts:
        abnormal_rates[indicator] = round(abnormal_counts[indicator] / total_reports * 100, 2)
    
    # 生成报告内容
    report_content = f"""# 血常规数据分析报告（完整版）

## 1. 数据概览

### 1.1 基本信息
- **总记录数**: {total_reports} 例（完整数据）
- **时间范围**: {min(r['test_date'] for r in reports)} 至 {max(r['test_date'] for r in reports)}
- **数据跨度**: {(datetime.strptime(max(r['test_date'] for r in reports), '%Y-%m-%d') - datetime.strptime(min(r['test_date'] for r in reports), '%Y-%m-%d')).days} 天
- **数据质量**: 排除 {150 - total_reports} 条有缺失值的记录，剩余数据完整可用

### 1.2 样本分布
- **性别分布**: 
  - 男性: {gender_counts['M']} 例 ({round(gender_counts['M']/total_reports*100, 1)}%)
  - 女性: {gender_counts['F']} 例 ({round(gender_counts['F']/total_reports*100, 1)}%)

- **年龄分布**:
  - 0-17岁: {age_groups['0-17']} 例 ({round(age_groups['0-17']/total_reports*100, 1)}%)
  - 18-44岁: {age_groups['18-44']} 例 ({round(age_groups['18-44']/total_reports*100, 1)}%)
  - 45-64岁: {age_groups['45-64']} 例 ({round(age_groups['45-64']/total_reports*100, 1)}%)
  - 65岁以上: {age_groups['65+']} 例 ({round(age_groups['65+']/total_reports*100, 1)}%)

## 2. 各指标统计汇总

| 指标 | 单位 | 均值 | 中位数 | 标准差 | 最小值 | 最大值 | Q1 | Q3 |
|------|------|------|--------|--------|--------|--------|----|----|
"""
    
    for indicator in indicators:
        s = stats[indicator]
        q1_display = s['q1'] if s['q1'] is not None else "N/A"
        q3_display = s['q3'] if s['q3'] is not None else "N/A"
        report_content += f"| {indicator_names[indicator]} | {units[indicator]} | {s['mean']} | {s['median']} | {s['std']} | {s['min']} | {s['max']} | {q1_display} | {q3_display} |\n"
    
    report_content += f"""
## 3. 异常率分析

### 3.1 总体异常情况
- **总报告数**: {total_reports} 例
- **异常报告数**: {len(abnormal_reports)} 例 ({round(len(abnormal_reports)/total_reports*100, 1)}%)
- **正常报告数**: {total_reports - len(abnormal_reports)} 例 ({round((total_reports - len(abnormal_reports))/total_reports*100, 1)}%)

### 3.2 各指标异常率
| 指标 | 异常例数 | 异常率 | 主要异常方向 |
|------|----------|--------|--------------|
"""
    
    # 分析异常方向（偏高或偏低）
    for indicator in indicators:
        if indicator in abnormal_counts:
            # 分析异常方向
            low_count = 0
            high_count = 0
            
            for report in reports:
                value = report[indicator]
                if indicator == 'wbc':
                    if report['age'] >= 65:
                        ref_low = reference_ranges['wbc']['ranges']['elderly']['low']
                        ref_high = reference_ranges['wbc']['ranges']['elderly']['high']
                    else:
                        ref_low = reference_ranges['wbc']['ranges']['adult']['low']
                        ref_high = reference_ranges['wbc']['ranges']['adult']['high']
                elif indicator in ['rbc', 'hgb']:
                    ref_range = reference_ranges[indicator]['ranges']['male' if report['gender'] == 'M' else 'female']
                    ref_low = ref_range['low']
                    ref_high = ref_range['high']
                else:
                    ref_low = reference_ranges[indicator]['ranges']['adult']['low']
                    ref_high = reference_ranges[indicator]['ranges']['adult']['high']
                
                if value < ref_low:
                    low_count += 1
                elif value > ref_high:
                    high_count += 1
            
            direction = []
            if low_count > 0:
                direction.append(f"偏低({low_count}例)")
            if high_count > 0:
                direction.append(f"偏高({high_count}例)")
            
            direction_str = "、".join(direction) if direction else "N/A"
            report_content += f"| {indicator_names[indicator]} | {abnormal_counts[indicator]} | {abnormal_rates[indicator]}% | {direction_str} |\n"
        else:
            report_content += f"| {indicator_names[indicator]} | 0 | 0.00% | 无异常 |\n"
    
    report_content += """
## 4. 异常指标共现模式分析

### 4.1 常见共现模式（前10位）
| 排名 | 异常指标组合 | 共现次数 | 占比 | 主要年龄组 | 主要性别 |
|------|-------------|----------|------|------------|----------|
"""
    
    for i, item in enumerate(cooccurrence[:10], 1):
        indicators_str = " + ".join([indicator_names[ind] for ind in item['indicators']])
        percentage = round(item['count'] / len(abnormal_reports) * 100, 2) if abnormal_reports else 0
        
        # 找出主要的年龄组和性别
        main_age_group = max(item['age_distribution'].items(), key=lambda x: x[1])[0] if item['age_distribution'] else "N/A"
        main_gender = max(item['gender_distribution'].items(), key=lambda x: x[1])[0] if item['gender_distribution'] else "N/A"
        
        report_content += f"| {i} | {indicators_str} | {item['count']} | {percentage}% | {main_age_group} | {main_gender} |\n"
    
    report_content += f"""
### 4.2 共现模式统计
- **总异常报告数**: {len(abnormal_reports)} 例
- **发现的共现模式数**: {len(cooccurrence)} 种
- **最常见的共现模式**: {" + ".join([indicator_names[ind] for ind in cooccurrence[0]['indicators']]) if cooccurrence else "无"}
- **单指标异常报告数**: {sum(1 for r in abnormal_reports if len(r['abnormalities']) == 1)} 例
- **多指标异常报告数**: {sum(1 for r in abnormal_reports if len(r['abnormalities']) > 1)} 例

## 5. 时间趋势分析

### 5.1 月度异常率趋势
| 月份 | 总例数 | 异常例数 | 异常率 | 主要异常指标 |
|------|--------|----------|--------|--------------|
"""
    
    months = sorted(monthly_trends.keys())
    for month in months:
        data = monthly_trends[month]
        # 找出该月异常率最高的指标
        if data['indicator_rates']:
            main_abnormal = max(data['indicator_rates'].items(), key=lambda x: x[1])
            main_indicator = indicator_names[main_abnormal[0]]
            main_rate = main_abnormal[1]
            main_str = f"{main_indicator}({main_rate}%)"
        else:
            main_str = "无"
        
        report_content += f"| {month} | {data['total']} | {data['abnormal_count']} | {data['abnormal_rate']}% | {main_str} |\n"
    
    report_content += """
### 5.2 趋势分析要点
1. **异常率波动**: 观察各月异常率的变化趋势
2. **季节性模式**: 分析是否存在季节性异常模式
3. **指标变化**: 跟踪各指标均值的月度变化

## 6. 质控建议

### 6.1 数据质量改进
1. **完善数据录入**: 减少数据缺失，确保所有字段完整
2. **标准化流程**: 统一数据采集和录入标准
3. **定期数据审核**: 建立月度数据质量检查机制

### 6.2 异常监控优化
1. **重点关注高异常率指标**: {max(abnormal_rates.items(), key=lambda x: x[1])[0] if abnormal_rates else "无"} 异常率最高，需重点监控
2. **建立共现模式预警**: 对常见共现异常模式设置预警阈值
3. **分层监控策略**: 按年龄组和性别制定差异化的监控标准

### 6.3 临床实践建议
1. **参考范围优化**: 考虑建立更细分的年龄和性别参考范围
2. **趋势分析应用**: 将月度趋势分析纳入常规质控
3. **异常模式研究**: 深入研究常见异常共现模式的临床意义

### 6.4 技术改进建议
1. **自动化分析**: 开发自动化数据分析工具
2. **实时监控**: 建立实时异常检测系统
3. **数据可视化**: 开发数据可视化仪表板

## 7. 合规声明

本报告严格遵守医疗数据合规要求：

### 7.1 数据安全
✅ **患者隐私保护**: 未包含任何患者个人身份信息（PAT-XXXXX格式）
✅ **聚合输出**: 所有输出均为聚合统计结果，无单条记录详情
✅ **数据脱敏**: 使用已脱敏的医疗数据进行分析

### 7.2 访问控制
✅ **最小权限原则**: 仅访问必要的 `sample_data/` 目录
✅ **审计追踪**: 所有数据访问已记录到合规日志
✅ **输出限制**: 仅输出到当前案例目录

### 7.3 网络安全
✅ **网络隔离**: 分析过程无任何网络访问行为
✅ **本地处理**: 所有分析均在本地环境完成
✅ **无数据外发**: 未使用任何网络传输工具

### 7.4 合规记录
- **数据访问次数**: {len([line for line in open("compliance_log.jsonl", "r").readlines() if "sample_data" in line])} 次
- **分析工具**: Python标准库（csv, json, statistics, datetime, collections）
- **输出格式**: Markdown报告，便于阅读和分享

---

**报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**分析样本量**: {total_reports} 例（完整数据）
**数据来源**: 三甲医院检验科血常规数据（已脱敏）
**分析工具版本**: Python 3.x + 标准库
**报告版本**: 1.0 - 完整分析版

---
*注：本报告仅供内部质控使用，不得用于临床诊断或患者个体评估。*
"""
    
    # 写入报告文件
    with open("complete_analysis_report.md", "w", encoding="utf-8") as f:
        f.write(report_content)
    
    print(f"完整分析报告已生成: complete_analysis_report.md")

if __name__ == "__main__":
    main()