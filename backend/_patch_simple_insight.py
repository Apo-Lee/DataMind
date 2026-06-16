import sys, re, os
os.chdir('E:\\Python_Code_Project\\DataMind\\backend')
sys.path.insert(0, '.')

with open('app/api/query.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the else block start
idx = content.find('    else:\n        report_md = None\n        if df is not None and not df.empty:')
if idx < 0:
    print('ERROR: cannot find target')
    sys.exit(1)

# Find the end of this block: '        if not report_md:'
end_idx = content.find('\n        if not report_md:', idx)
if end_idx < 0:
    print('ERROR: cannot find end')
    sys.exit(1)

# Find the two lines after 'if not report_md:'
after = content[end_idx:]
next_newline = after.index('\n', 1)
line2_end = after.index('\n', next_newline + 1)
block_end = end_idx + line2_end + 1

old_block = content[idx:block_end]
print('Old block length:', len(old_block))

new_insight = '''    else:
        report_md = None
        if df is not None and not df.empty:
            insights.append({"type": "table", "content": df.head(50).to_dict(orient="records")})
            # 简单查询也调用 LLM 生成分析话语，提升用户体验
            simple_insight = ""
            try:
                sp = (
                    "你是一位数据分析助手。根据用户问题与查询结果，用2-3句中文给出简洁的分析总结。"
                    + chr(10) + chr(10)
                    + "用户问题: " + str(body.question) + chr(10)
                    + "查询结果: " + str(len(df)) + " 行, 列: " + str(list(df.columns)) + chr(10)
                    + "数据样例: " + str(df.head(5).to_dict(orient="records")) + chr(10) + chr(10)
                    + "要求:" + chr(10)
                    + "1. 提炼关键数字（总数、平均值、最大值、最小值等）" + chr(10)
                    + "2. 指出明显趋势或分布特征" + chr(10)
                    + "3. 不编造数据，严格基于提供的数据" + chr(10)
                    + "4. 口语化中文，不用 Markdown 格式" + chr(10)
                    + "5. 如果数据为空，说明可能原因"
                )
                resp = await llm_client.chat([
                    {"role": "system", "content": "你是一位专业的数据分析师。"},
                    {"role": "user", "content": sp},
                ])
                simple_insight = resp.get("content", "")
            except Exception as e:
                logger.warning("simple insight generation failed: %s", e)
            
            analysis_for_report = {
                "status": "success",
                "data": {
                    "insight": simple_insight,
                    "table": [],
                }
            }
            try:
                report_md = await assemble_report(
                    question=body.question, sql=sql, df=df,
                    intent=intent, analysis_result=analysis_for_report,
                )
            except Exception as e:
                logger.warning("assemble_report failed: %s", e)
        if not report_md:
            report_md = _build_simple_report(body.question, sql, df)
'''

content = content[:idx] + new_insight + content[block_end:]

with open('app/api/query.py', 'w', encoding='utf-8') as f:
    f.write(content)

compile(content, 'query.py', 'exec')
print('COMPILE OK!')
print('Done')
