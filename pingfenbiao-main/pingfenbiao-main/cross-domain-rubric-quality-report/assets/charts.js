// assets/charts.js
(function() {
    var style = getComputedStyle(document.documentElement);
    var accent = style.getPropertyValue('--accent').trim();
    var accent2 = style.getPropertyValue('--accent2').trim();
    var ink = style.getPropertyValue('--ink').trim();
    var muted = style.getPropertyValue('--muted').trim();
    var rule = style.getPropertyValue('--rule').trim();
    var bg2 = style.getPropertyValue('--bg2').trim();

    // --- Chart 1: 维度评分项对比 ---
    var chart1 = echarts.init(document.getElementById('chart-dim-compare'), null, { renderer: 'svg' });
    chart1.setOption({
        animation: false,
        tooltip: { trigger: 'axis', appendToBody: true },
        legend: {
            data: ['样例评分表', '生成评分表'],
            textStyle: { color: ink },
            top: 0
        },
        grid: { left: 60, right: 20, top: 40, bottom: 30 },
        xAxis: {
            type: 'category',
            data: ['信息获取', '科学推理', '报告综合'],
            axisLabel: { color: muted },
            axisLine: { lineStyle: { color: rule } }
        },
        yAxis: {
            type: 'value',
            name: '评分项数量',
            nameTextStyle: { color: muted },
            axisLabel: { color: muted },
            splitLine: { lineStyle: { color: rule } }
        },
        series: [
            {
                name: '样例评分表',
                type: 'bar',
                data: [15, 25, 10],
                itemStyle: { color: accent2 },
                barWidth: '30%'
            },
            {
                name: '生成评分表',
                type: 'bar',
                data: [10, 22, 10],
                itemStyle: { color: accent },
                barWidth: '30%'
            }
        ]
    });
    window.addEventListener('resize', function() { chart1.resize(); });

    // --- Chart 2: Role分布对比 ---
    var chart2 = echarts.init(document.getElementById('chart-role-compare'), null, { renderer: 'svg' });
    chart2.setOption({
        animation: false,
        tooltip: { trigger: 'axis', appendToBody: true },
        legend: {
            data: ['样例-信息获取', '生成-信息获取', '样例-科学推理', '生成-科学推理', '样例-报告综合', '生成-报告综合'],
            textStyle: { color: muted, fontSize: 11 },
            top: 0,
            type: 'scroll'
        },
        grid: { left: 60, right: 20, top: 60, bottom: 30 },
        xAxis: {
            type: 'category',
            data: ['Critical', 'Mandatory', 'Standard'],
            axisLabel: { color: muted },
            axisLine: { lineStyle: { color: rule } }
        },
        yAxis: {
            type: 'value',
            name: '占比 (%)',
            nameTextStyle: { color: muted },
            axisLabel: { color: muted, formatter: '{value}%' },
            splitLine: { lineStyle: { color: rule } },
            max: 100
        },
        series: [
            {
                name: '样例-信息获取',
                type: 'bar',
                data: [20, 47, 33],
                itemStyle: { color: accent2 + '99' },
                barWidth: '10%'
            },
            {
                name: '生成-信息获取',
                type: 'bar',
                data: [10, 70, 20],
                itemStyle: { color: accent },
                barWidth: '10%'
            },
            {
                name: '样例-科学推理',
                type: 'bar',
                data: [56, 32, 12],
                itemStyle: { color: accent2 + 'cc' },
                barWidth: '10%'
            },
            {
                name: '生成-科学推理',
                type: 'bar',
                data: [36, 45, 18],
                itemStyle: { color: accent + 'cc' },
                barWidth: '10%'
            },
            {
                name: '样例-报告综合',
                type: 'bar',
                data: [0, 40, 60],
                itemStyle: { color: accent2 + '66' },
                barWidth: '10%'
            },
            {
                name: '生成-报告综合',
                type: 'bar',
                data: [0, 50, 50],
                itemStyle: { color: accent + '66' },
                barWidth: '10%'
            }
        ]
    });
    window.addEventListener('resize', function() { chart2.resize(); });

    // --- Chart 3: 质量雷达图 ---
    var chart3 = echarts.init(document.getElementById('chart-quality-radar'), null, { renderer: 'svg' });
    chart3.setOption({
        animation: false,
        tooltip: { appendToBody: true },
        legend: {
            data: ['样例评分表', '生成评分表'],
            textStyle: { color: ink },
            top: 0
        },
        radar: {
            indicator: [
                { name: '结构完整性', max: 100 },
                { name: '领域准确性', max: 100 },
                { name: '科学深度', max: 100 },
                { name: '判定标准', max: 100 },
                { name: '能力分类', max: 100 },
                { name: 'Role均衡', max: 100 },
                { name: '去重质量', max: 100 }
            ],
            axisName: { color: ink, fontSize: 12 },
            splitLine: { lineStyle: { color: rule } },
            splitArea: { areaStyle: { color: [bg2, 'transparent'] } },
            axisLine: { lineStyle: { color: rule } }
        },
        series: [{
            type: 'radar',
            data: [
                {
                    value: [95, 90, 85, 50, 30, 80, 75],
                    name: '样例评分表',
                    lineStyle: { color: accent2 },
                    itemStyle: { color: accent2 },
                    areaStyle: { color: accent2 + '33' }
                },
                {
                    value: [90, 90, 85, 95, 100, 65, 75],
                    name: '生成评分表',
                    lineStyle: { color: accent },
                    itemStyle: { color: accent },
                    areaStyle: { color: accent + '33' }
                }
            ]
        }]
    });
    window.addEventListener('resize', function() { chart3.resize(); });

    // --- Chart 4: 问题类型分布 ---
    var chart4 = echarts.init(document.getElementById('chart-question-types'), null, { renderer: 'svg' });
    chart4.setOption({
        animation: false,
        tooltip: { trigger: 'item', appendToBody: true },
        legend: {
            orient: 'vertical',
            right: 10,
            top: 'center',
            textStyle: { color: muted, fontSize: 12 }
        },
        series: [
            {
                name: '生成评分表问题类型',
                type: 'pie',
                radius: ['40%', '70%'],
                center: ['35%', '50%'],
                avoidLabelOverlap: false,
                itemStyle: { borderRadius: 4, borderColor: bg2, borderWidth: 2 },
                label: { show: false },
                emphasis: {
                    label: { show: true, fontSize: 14, fontWeight: 'bold', color: ink }
                },
                labelLine: { show: false },
                data: [
                    { value: 19, name: '评估类', itemStyle: { color: accent } },
                    { value: 5, name: '描述/陈述/识别', itemStyle: { color: accent + 'cc' } },
                    { value: 4, name: '对比/分析', itemStyle: { color: accent + '99' } },
                    { value: 4, name: '准确性/结构', itemStyle: { color: accent2 } },
                    { value: 6, name: '其他类型', itemStyle: { color: accent2 + '99' } }
                ]
            }
        ]
    });
    window.addEventListener('resize', function() { chart4.resize(); });
})();
