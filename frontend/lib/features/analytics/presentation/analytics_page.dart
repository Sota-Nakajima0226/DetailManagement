import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_providers.dart';
import '../../../core/presentation/main_app_bar_actions.dart';
import '../../statements/data/statements_api.dart';
import '../../statements/models/card_issuer.dart';
import '../../statements/models/category_item.dart';
import '../../statements/presentation/upload_status_badge.dart';
import '../../upload/models/upload_status.dart';

class AnalyticsPage extends ConsumerStatefulWidget {
  const AnalyticsPage({super.key});

  @override
  ConsumerState<AnalyticsPage> createState() => _AnalyticsPageState();
}

enum _AnalyticsTab { byCategory, monthlyTrend }

class _AnalyticsPageState extends ConsumerState<AnalyticsPage> {
  late final StatementsApi _api;
  final DateTime _now = DateTime.now();
  late int _year;
  late int _month;
  String? _cardIssuer;
  bool _loading = false;
  String? _error;
  String? _statusError;
  List<dynamic> _categoryTotals = <dynamic>[];
  List<dynamic> _holderTotals = <dynamic>[];
  List<dynamic> _trendSeries = <dynamic>[];
  List<CategoryItem> _categories = <CategoryItem>[];
  List<CardIssuer> _issuers = <CardIssuer>[];
  UploadStatus? _uploadStatus;
  _AnalyticsTab _selectedTab = _AnalyticsTab.byCategory;
  int? _focusedPieIndex;

  /// 明細も、手動・固定費を含む当月合計も無いときだけ未アップロード文言にする。
  bool get _showMissingUploadMessage =>
      _uploadStatus != null &&
      _uploadStatus!.uploaded.isEmpty &&
      _categoryTotals.isEmpty;

  @override
  void initState() {
    super.initState();
    _api = ref.read(statementsApiProvider);
    _year = _now.year;
    _month = _now.month;
    _load();
  }

  Future<void> _changeMonth(int delta) async {
    final next = DateTime(_year, _month + delta, 1);
    setState(() {
      _year = next.year;
      _month = next.month;
    });
    await _load();
  }

  Future<void> _load() async {
    final year = _year;
    final month = _month;
    final issuer = _cardIssuer;
    setState(() {
      _loading = true;
      _error = null;
      _statusError = null;
      _uploadStatus = null;
    });
    try {
      UploadStatus? status;
      try {
        status = await _api.fetchUploadStatus(year: year, month: month);
      } catch (e) {
        if (!mounted || year != _year || month != _month) return;
        setState(() => _statusError = '取込状況の取得に失敗しました: $e');
      }
      if (!mounted || year != _year || month != _month) return;

      final issuers = await _api.fetchCardIssuers();
      if (!mounted || year != _year || month != _month) return;

      final fromDate = DateTime(year, month - 5);
      final categories = await _api.fetchCategories();
      final category = await _api.fetchCategorySummary(
        year: year,
        month: month,
        cardIssuer: issuer,
      );
      final holder = await _api.fetchHolderSummary(
        year: year,
        month: month,
        cardIssuer: issuer,
      );
      final trend = await _api.fetchMonthlyTrend(
        fromYear: fromDate.year,
        fromMonth: fromDate.month,
        toYear: year,
        toMonth: month,
        cardIssuer: issuer,
      );
      if (!mounted || year != _year || month != _month) return;
      setState(() {
        _issuers = issuers;
        _uploadStatus = status;
        _categories = categories;
        _categoryTotals = (category['totals'] as List<dynamic>? ?? <dynamic>[]);
        _holderTotals = (holder['totals'] as List<dynamic>? ?? <dynamic>[]);
        _trendSeries = (trend['series'] as List<dynamic>? ?? <dynamic>[]);
        _focusedPieIndex = null;
      });
    } catch (e) {
      if (!mounted || year != _year || month != _month) return;
      setState(() {
        _error = '集計取得に失敗しました: $e';
      });
    } finally {
      if (mounted && year == _year && month == _month) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  /// `#RRGGBB` または `#RRGGBBAA` を [Color] に変換する。
  Color _hexToColor(String hex) {
    var v = hex.replaceFirst('#', '').trim();
    if (v.length == 6) v = 'FF$v';
    final parsed = int.tryParse(v, radix: 16);
    if (parsed == null) return Colors.grey;
    return Color(parsed);
  }

  String _formatYAxis(double v) {
    if (v >= 10000) {
      return '${(v / 10000).toStringAsFixed(v % 10000 == 0 ? 0 : 1)}万';
    }
    return v.toInt().toString();
  }

  /// 1234567 -> "1,234,567"
  String _formatThousands(int v) {
    final s = v.toString();
    final buffer = StringBuffer();
    for (var i = 0; i < s.length; i++) {
      if (i != 0 && (s.length - i) % 3 == 0) buffer.write(',');
      buffer.write(s[i]);
    }
    return buffer.toString();
  }

  Color _categoryColorById(int? id) {
    if (id == null) return Colors.grey;
    for (final c in _categories) {
      if (c.id == id) return _hexToColor(c.color);
    }
    return Colors.blueGrey;
  }

  List<Map<String, dynamic>> _categoryTotalsAsMap() {
    return _categoryTotals
        .map((row) => row as Map<String, dynamic>)
        .toList(growable: false);
  }

  @override
  Widget build(BuildContext context) {
    final years = List<int>.generate(5, (i) => _now.year - 2 + i);
    final months = List<int>.generate(12, (i) => i + 1);
    final categoryTotalSum = _categoryTotals.fold<int>(
      0,
      (sum, row) =>
          sum + ((row as Map<String, dynamic>)['amount'] as int? ?? 0),
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('グラフ・集計'),
        actions: buildMainAppBarActions(context, ref),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(8, 4, 8, 16),
        children: [
          Row(
            children: [
              IconButton(
                visualDensity: VisualDensity.compact,
                onPressed: _loading ? null : () => _changeMonth(-1),
                icon: const Icon(Icons.chevron_left),
              ),
              Expanded(
                child: DropdownButtonFormField<int>(
                  value: _year,
                  isDense: true,
                  items: years
                      .map((y) =>
                          DropdownMenuItem(value: y, child: Text(y.toString())))
                      .toList(),
                  onChanged: (v) async {
                    if (v == null) return;
                    setState(() => _year = v);
                    await _load();
                  },
                  decoration: const InputDecoration(
                    labelText: '年',
                    isDense: true,
                    contentPadding:
                        EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: DropdownButtonFormField<int>(
                  value: _month,
                  isDense: true,
                  items: months
                      .map((m) =>
                          DropdownMenuItem(value: m, child: Text(m.toString())))
                      .toList(),
                  onChanged: (v) async {
                    if (v == null) return;
                    setState(() => _month = v);
                    await _load();
                  },
                  decoration: const InputDecoration(
                    labelText: '月',
                    isDense: true,
                    contentPadding:
                        EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                ),
              ),
              IconButton(
                visualDensity: VisualDensity.compact,
                onPressed: _loading ? null : () => _changeMonth(1),
                icon: const Icon(Icons.chevron_right),
              ),
            ],
          ),
          const SizedBox(height: 8),
          DropdownButtonFormField<String?>(
            value: _issuers.any((issuer) => issuer.code == _cardIssuer)
                ? _cardIssuer
                : null,
            isDense: true,
            decoration: const InputDecoration(
              labelText: 'カード発行会社',
              isDense: true,
              contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            ),
            items: [
              const DropdownMenuItem<String?>(
                value: null,
                child: Text('すべて'),
              ),
              for (final issuer in _issuers)
                DropdownMenuItem<String?>(
                  value: issuer.code,
                  child: Text(issuer.displayName),
                ),
            ],
            onChanged: _loading
                ? null
                : (value) async {
                    setState(() => _cardIssuer = value);
                    await _load();
                  },
          ),
          const SizedBox(height: 8),
          UploadStatusBadge(
            status: _uploadStatus,
            isLoading: _loading && _uploadStatus == null,
          ),
          if (_statusError != null) ...[
            const SizedBox(height: 8),
            Text(
              _statusError!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ],
          const SizedBox(height: 8),
          if (_loading) const Center(child: CircularProgressIndicator()),
          if (!_loading && _showMissingUploadMessage)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 48, horizontal: 16),
              child: Column(
                children: [
                  Icon(
                    Icons.inbox_outlined,
                    size: 64,
                    color: Theme.of(context).colorScheme.outline,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    '対象年月の明細はまだアップロードされていません',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodyLarge,
                  ),
                ],
              ),
            ),
          if (!_loading && !_showMissingUploadMessage) ...[
            Center(
              child: SegmentedButton<_AnalyticsTab>(
                style: SegmentedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 8,
                  ),
                  visualDensity: VisualDensity.compact,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                segments: const [
                  ButtonSegment(
                    value: _AnalyticsTab.byCategory,
                    label: Text(
                      'カテゴリ別',
                      maxLines: 1,
                      softWrap: false,
                      overflow: TextOverflow.visible,
                    ),
                  ),
                  ButtonSegment(
                    value: _AnalyticsTab.monthlyTrend,
                    label: Text(
                      '月次推移',
                      maxLines: 1,
                      softWrap: false,
                      overflow: TextOverflow.visible,
                    ),
                  ),
                ],
                selected: <_AnalyticsTab>{_selectedTab},
                onSelectionChanged: (selection) {
                  setState(() => _selectedTab = selection.first);
                },
              ),
            ),
            const SizedBox(height: 12),
            _buildMonthTotalCard(categoryTotalSum),
            const SizedBox(height: 12),
            if (_selectedTab == _AnalyticsTab.byCategory) ...[
              _buildCategoryPieChart(),
              const SizedBox(height: 12),
              _buildCategorySummaryCard(),
              const SizedBox(height: 12),
              _buildHolderSummaryCard(),
            ],
            if (_selectedTab == _AnalyticsTab.monthlyTrend) ...[
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: _buildMonthlyTrendChart(),
                ),
              ),
              const SizedBox(height: 12),
              _buildHolderSummaryCard(),
            ],
          ],
        ],
      ),
    );
  }

  Widget _buildMonthTotalCard(int total) {
    final theme = Theme.of(context);
    return Card(
      color: theme.colorScheme.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            Icon(
              Icons.account_balance_wallet_outlined,
              color: theme.colorScheme.onPrimaryContainer,
            ),
            const SizedBox(width: 12),
            Text(
              '$_year年$_month月の合計',
              style: theme.textTheme.titleSmall?.copyWith(
                color: theme.colorScheme.onPrimaryContainer,
              ),
            ),
            const Spacer(),
            Text(
              '${_formatThousands(total)} 円',
              style: theme.textTheme.titleMedium?.copyWith(
                color: theme.colorScheme.onPrimaryContainer,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCategoryPieChart() {
    final visibleTotals = _categoryTotalsAsMap()
        .where((m) => (m['amount'] as int? ?? 0) > 0)
        .toList(growable: false);
    final total = visibleTotals.fold<int>(
      0,
      (sum, row) => sum + (row['amount'] as int? ?? 0),
    );
    if (total == 0) return const SizedBox.shrink();

    final focusedIndex =
        (_focusedPieIndex != null && _focusedPieIndex! < visibleTotals.length)
            ? _focusedPieIndex
            : null;

    final sections = <PieChartSectionData>[];
    for (var i = 0; i < visibleTotals.length; i++) {
      final m = visibleTotals[i];
      final amount = (m['amount'] as int? ?? 0).toDouble();
      final pct = amount / total * 100;
      final color = _categoryColorById(m['category_id'] as int?);
      final isFocused = focusedIndex == i;
      sections.add(
        PieChartSectionData(
          color: color,
          value: amount,
          title: pct >= 5 ? '${pct.toStringAsFixed(0)}%' : '',
          titleStyle: TextStyle(
            fontSize: isFocused ? 14 : 12,
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
          radius: isFocused ? 82 : 70,
        ),
      );
    }

    Widget detailRow;
    if (focusedIndex != null) {
      final m = visibleTotals[focusedIndex];
      final amount = m['amount'] as int? ?? 0;
      final pct = amount / total * 100;
      final name = m['category_name'] as String? ?? '未分類';
      final color = _categoryColorById(m['category_id'] as int?);
      detailRow = Row(
        children: [
          Container(
            width: 12,
            height: 12,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              '$name: ${_formatThousands(amount)} 円 (${pct.toStringAsFixed(1)}%)',
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      );
    } else {
      detailRow = Text(
        'スライスをタップでカテゴリ詳細を表示',
        style: TextStyle(
          fontSize: 12,
          color: Theme.of(context).colorScheme.outline,
        ),
      );
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('カテゴリ別構成'),
            const SizedBox(height: 12),
            SizedBox(
              height: 220,
              child: PieChart(
                PieChartData(
                  sections: sections,
                  centerSpaceRadius: 40,
                  sectionsSpace: 2,
                  pieTouchData: PieTouchData(
                    enabled: true,
                    touchCallback: (event, response) {
                      if (event is! FlTapUpEvent) return;
                      setState(() {
                        final section = response?.touchedSection;
                        if (section == null ||
                            section.touchedSectionIndex < 0) {
                          _focusedPieIndex = null;
                          return;
                        }
                        final i = section.touchedSectionIndex;
                        _focusedPieIndex = (_focusedPieIndex == i) ? null : i;
                      });
                    },
                  ),
                ),
              ),
            ),
            const SizedBox(height: 8),
            detailRow,
          ],
        ),
      ),
    );
  }

  Widget _buildCategorySummaryCard() {
    final totals = _categoryTotalsAsMap();
    final maxCategory = totals.isEmpty
        ? 1
        : totals
            .map((e) => e['amount'] as int? ?? 0)
            .reduce((a, b) => a > b ? a : b);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('カテゴリ別'),
            const SizedBox(height: 8),
            ...totals.map((m) {
              final amount = m['amount'] as int? ?? 0;
              final rate = amount / maxCategory;
              final color = _categoryColorById(m['category_id'] as int?);
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 10,
                          height: 10,
                          decoration: BoxDecoration(
                            color: color,
                            borderRadius: BorderRadius.circular(2),
                          ),
                        ),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text('${m['category_name']}'),
                        ),
                        Text('${_formatThousands(amount)} 円'),
                      ],
                    ),
                    const SizedBox(height: 2),
                    LinearProgressIndicator(
                      value: rate.clamp(0, 1).toDouble(),
                      backgroundColor: color.withValues(alpha: 0.15),
                      valueColor: AlwaysStoppedAnimation<Color>(color),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  Widget _buildHolderSummaryCard() {
    final holderTotalSum = _holderTotals.fold<int>(
      0,
      (sum, row) =>
          sum + ((row as Map<String, dynamic>)['amount'] as int? ?? 0),
    );
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('名義人別合計'),
            const SizedBox(height: 8),
            ..._holderTotals.map((row) {
              final m = row as Map<String, dynamic>;
              final amount = m['amount'] as int? ?? 0;
              final percent =
                  holderTotalSum == 0 ? 0.0 : amount / holderTotalSum * 100;
              return ListTile(
                dense: true,
                title: Text('${m['card_holder']}'),
                trailing: Text(
                  '${_formatThousands(amount)} 円 (${percent.toStringAsFixed(1)}%)',
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  /// 過去6ヶ月のカテゴリ別積み上げ棒グラフ。
  Widget _buildMonthlyTrendChart() {
    final months = List<DateTime>.generate(
      6,
      (i) => DateTime(_year, _month - 5 + i, 1),
    );

    final categoryMeta = <int?, ({String name, Color color, int sortOrder})>{};
    for (final c in _categories) {
      categoryMeta[c.id] = (
        name: c.name,
        color: _hexToColor(c.color),
        sortOrder: c.sortOrder,
      );
    }

    final monthCategoryAmount = <String, Map<int?, int>>{};
    final categoryOrder = <int?>[];
    for (final s in _trendSeries) {
      final m = s as Map<String, dynamic>;
      final catId = m['category_id'] as int?;
      final catName = m['category_name'] as String? ?? '未分類';
      categoryMeta.putIfAbsent(
        catId,
        () => (
          name: catName,
          color: catId == null ? Colors.grey : Colors.blueGrey,
          sortOrder: 9999,
        ),
      );
      if (!categoryOrder.contains(catId)) {
        categoryOrder.add(catId);
      }
      final points = m['points'] as List<dynamic>? ?? const <dynamic>[];
      for (final p in points) {
        final pm = p as Map<String, dynamic>;
        final ymKey = '${pm['year']}-${pm['month']}';
        monthCategoryAmount.putIfAbsent(ymKey, () => <int?, int>{});
        monthCategoryAmount[ymKey]![catId] = pm['amount'] as int? ?? 0;
      }
    }

    categoryOrder.sort((a, b) {
      final aOrder = categoryMeta[a]?.sortOrder ?? 9999;
      final bOrder = categoryMeta[b]?.sortOrder ?? 9999;
      return aOrder.compareTo(bOrder);
    });

    double maxY = 0;
    final barGroups = <BarChartGroupData>[];
    for (var i = 0; i < months.length; i++) {
      final ym = months[i];
      final ymKey = '${ym.year}-${ym.month}';
      final perCat = monthCategoryAmount[ymKey] ?? <int?, int>{};
      double cumulative = 0;
      final stackItems = <BarChartRodStackItem>[];
      for (final catId in categoryOrder) {
        final amount = (perCat[catId] ?? 0).toDouble();
        if (amount <= 0) continue;
        final color = categoryMeta[catId]?.color ?? Colors.grey;
        stackItems.add(
          BarChartRodStackItem(cumulative, cumulative + amount, color),
        );
        cumulative += amount;
      }
      if (cumulative > maxY) maxY = cumulative;
      barGroups.add(
        BarChartGroupData(
          x: i,
          barRods: [
            BarChartRodData(
              toY: cumulative,
              width: 22,
              color: stackItems.isEmpty
                  ? Theme.of(context).colorScheme.surfaceContainerHighest
                  : null,
              rodStackItems: stackItems,
              borderRadius: const BorderRadius.vertical(
                top: Radius.circular(2),
              ),
            ),
          ],
        ),
      );
    }

    if (maxY == 0) maxY = 1;
    final yInterval = (maxY / 4).ceilToDouble();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('月次推移（過去6ヶ月・カテゴリ別積み上げ）'),
        const SizedBox(height: 12),
        SizedBox(
          height: 260,
          child: BarChart(
            BarChartData(
              maxY: maxY * 1.15,
              barGroups: barGroups,
              alignment: BarChartAlignment.spaceAround,
              gridData: FlGridData(
                show: true,
                drawVerticalLine: false,
                horizontalInterval: yInterval,
              ),
              borderData: FlBorderData(show: false),
              titlesData: FlTitlesData(
                leftTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 44,
                    interval: yInterval,
                    getTitlesWidget: (value, meta) {
                      if (value == 0) return const SizedBox.shrink();
                      return Padding(
                        padding: const EdgeInsets.only(right: 4),
                        child: Text(
                          _formatYAxis(value),
                          style: const TextStyle(fontSize: 10),
                        ),
                      );
                    },
                  ),
                ),
                bottomTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 22,
                    getTitlesWidget: (value, meta) {
                      final idx = value.toInt();
                      if (idx < 0 || idx >= months.length) {
                        return const SizedBox.shrink();
                      }
                      return Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text(
                          '${months[idx].month}月',
                          style: const TextStyle(fontSize: 10),
                        ),
                      );
                    },
                  ),
                ),
                rightTitles: const AxisTitles(),
                topTitles: const AxisTitles(),
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        if (categoryOrder.isNotEmpty)
          Wrap(
            spacing: 12,
            runSpacing: 6,
            children: categoryOrder.map((catId) {
              final meta = categoryMeta[catId]!;
              return Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 12,
                    height: 12,
                    decoration: BoxDecoration(
                      color: meta.color,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                  const SizedBox(width: 4),
                  Text(meta.name, style: const TextStyle(fontSize: 12)),
                ],
              );
            }).toList(),
          ),
      ],
    );
  }
}
