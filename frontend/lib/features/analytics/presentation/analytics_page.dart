import 'package:flutter/material.dart';

import '../../statements/data/statements_api.dart';

class AnalyticsPage extends StatefulWidget {
  const AnalyticsPage({super.key});

  @override
  State<AnalyticsPage> createState() => _AnalyticsPageState();
}

class _AnalyticsPageState extends State<AnalyticsPage> {
  final StatementsApi _api = StatementsApi();
  final DateTime _now = DateTime.now();
  late int _year;
  late int _month;
  bool _loading = false;
  String? _error;
  List<dynamic> _categoryTotals = <dynamic>[];
  List<dynamic> _holderTotals = <dynamic>[];
  List<dynamic> _trendSeries = <dynamic>[];

  @override
  void initState() {
    super.initState();
    _year = _now.year;
    _month = _now.month;
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final fromDate = DateTime(_year, _month - 5);
      final category = await _api.fetchCategorySummary(year: _year, month: _month);
      final holder = await _api.fetchHolderSummary(year: _year, month: _month);
      final trend = await _api.fetchMonthlyTrend(
        fromYear: fromDate.year,
        fromMonth: fromDate.month,
        toYear: _year,
        toMonth: _month,
      );
      if (!mounted) return;
      setState(() {
        _categoryTotals = (category['totals'] as List<dynamic>? ?? <dynamic>[]);
        _holderTotals = (holder['totals'] as List<dynamic>? ?? <dynamic>[]);
        _trendSeries = (trend['series'] as List<dynamic>? ?? <dynamic>[]);
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '集計取得に失敗しました: $e';
      });
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final years = List<int>.generate(5, (i) => _now.year - 2 + i);
    final months = List<int>.generate(12, (i) => i + 1);
    final maxCategory = _categoryTotals.isEmpty
        ? 1
        : _categoryTotals
            .map((e) => (e as Map<String, dynamic>)['amount'] as int? ?? 0)
            .reduce((a, b) => a > b ? a : b);

    return Scaffold(
      appBar: AppBar(title: const Text('グラフ・集計')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<int>(
                  value: _year,
                  items: years
                      .map((y) => DropdownMenuItem(value: y, child: Text(y.toString())))
                      .toList(),
                  onChanged: (v) => setState(() => _year = v ?? _year),
                  decoration: const InputDecoration(labelText: '年'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: DropdownButtonFormField<int>(
                  value: _month,
                  items: months
                      .map((m) => DropdownMenuItem(value: m, child: Text(m.toString())))
                      .toList(),
                  onChanged: (v) => setState(() => _month = v ?? _month),
                  decoration: const InputDecoration(labelText: '月'),
                ),
              ),
              const SizedBox(width: 12),
              ElevatedButton(onPressed: _loading ? null : _load, child: const Text('更新')),
            ],
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ],
          const SizedBox(height: 16),
          if (_loading) const Center(child: CircularProgressIndicator()),
          if (!_loading) ...[
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('カテゴリ別（円グラフ相当）'),
                    const SizedBox(height: 8),
                    ..._categoryTotals.map((row) {
                      final m = row as Map<String, dynamic>;
                      final amount = m['amount'] as int? ?? 0;
                      final rate = amount / maxCategory;
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('${m['category_name']}: $amount 円'),
                            LinearProgressIndicator(value: rate.clamp(0, 1).toDouble()),
                          ],
                        ),
                      );
                    }),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('名義人別合計'),
                    const SizedBox(height: 8),
                    ..._holderTotals.map((row) {
                      final m = row as Map<String, dynamic>;
                      return ListTile(
                        dense: true,
                        title: Text('${m['card_holder']}'),
                        trailing: Text('${m['amount']} 円'),
                      );
                    }),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('月次推移（棒グラフ相当）'),
                    const SizedBox(height: 8),
                    ..._trendSeries.take(3).map((row) {
                      final m = row as Map<String, dynamic>;
                      final points = m['points'] as List<dynamic>? ?? <dynamic>[];
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${m['category_name']}'),
                          Wrap(
                            spacing: 8,
                            children: points.map((p) {
                              final pm = p as Map<String, dynamic>;
                              return Chip(
                                label: Text(
                                  '${pm['year']}/${pm['month']}: ${pm['amount']}',
                                ),
                              );
                            }).toList(),
                          ),
                          const SizedBox(height: 8),
                        ],
                      );
                    }),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
