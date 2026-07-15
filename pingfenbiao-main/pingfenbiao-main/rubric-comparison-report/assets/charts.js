(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var green = style.getPropertyValue('--green').trim();
  var orange = style.getPropertyValue('--orange').trim();

  // --- Chart 1: Source Coverage ---
  var chart1 = echarts.init(document.getElementById('chart-source'), null, { renderer: 'svg' });
  chart1.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      appendToBody: true,
      formatter: function(params) {
        var s = '<b>' + params[0].name + '</b><br/>';
        params.forEach(function(p) {
          s += p.marker + ' ' + p.seriesName + ': ' + p.value + '%<br/>';
        });
        return s;
      }
    },
    legend: {
      data: ['source_ids 覆盖率', '多源引用率', 'SR 多源引用率'],
      bottom: 0,
      textStyle: { color: muted, fontSize: 11 }
    },
    grid: { left: 50, right: 30, top: 20, bottom: 50 },
    xAxis: {
      type: 'category',
      data: ['v5_3_rollback', 'v5_3 历史最佳', 'v1 最佳版本', '样例'],
      axisLabel: { color: muted, fontSize: 10, rotate: 0 },
      axisLine: { lineStyle: { color: rule } }
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: { color: muted, fontSize: 10, formatter: '{value}%' },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    series: [
      {
        name: 'source_ids 覆盖率',
        type: 'bar',
        data: [67, 82, 100, 90],
        itemStyle: { color: accent, borderRadius: [4, 4, 0, 0] },
        barWidth: 24
      },
      {
        name: '多源引用率',
        type: 'bar',
        data: [30, 44, 48, 32],
        itemStyle: { color: accent + '99', borderRadius: [4, 4, 0, 0] },
        barWidth: 24
      },
      {
        name: 'SR 多源引用率',
        type: 'line',
        data: [60, 74, 57, 52],
        lineStyle: { color: accent2, width: 2 },
        symbol: 'circle',
        symbolSize: 8,
        itemStyle: { color: accent2, borderColor: '#fff', borderWidth: 2 }
      }
    ]
  });
  window.addEventListener('resize', function() { chart1.resize(); });

  // --- Chart 2: Quality-Driven vs Content-Driven ---
  var chart2 = echarts.init(document.getElementById('chart-quality'), null, { renderer: 'svg' });
  chart2.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      appendToBody: true,
      formatter: function(params) {
        var s = '<b>' + params[0].name + '</b><br/>';
        params.forEach(function(p) {
          s += p.marker + ' ' + p.seriesName + ': ' + p.value + '%<br/>';
        });
        return s;
      }
    },
    legend: {
      data: ['Quality-Driven', 'Content-Driven'],
      bottom: 0,
      textStyle: { color: muted, fontSize: 11 }
    },
    grid: { left: 50, right: 30, top: 20, bottom: 50 },
    xAxis: {
      type: 'category',
      data: ['v5_3_rollback', 'v5_3 历史最佳', 'v1 最佳版本', '样例'],
      axisLabel: { color: muted, fontSize: 10 },
      axisLine: { lineStyle: { color: rule } }
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: { color: muted, fontSize: 10, formatter: '{value}%' },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    series: [
      {
        name: 'Quality-Driven',
        type: 'bar',
        stack: 'total',
        data: [75, 77, 62, 50],
        itemStyle: { color: green, borderRadius: [4, 4, 0, 0] },
        barWidth: 36,
        label: {
          show: true,
          position: 'inside',
          formatter: '{c}%',
          color: '#fff',
          fontSize: 12,
          fontWeight: 700
        }
      },
      {
        name: 'Content-Driven',
        type: 'bar',
        stack: 'total',
        data: [25, 23, 38, 50],
        itemStyle: { color: bg2, borderRadius: [0, 0, 4, 4] },
        barWidth: 36,
        label: {
          show: true,
          position: 'inside',
          formatter: '{c}%',
          color: muted,
          fontSize: 11
        }
      }
    ]
  });
  window.addEventListener('resize', function() { chart2.resize(); });
})();