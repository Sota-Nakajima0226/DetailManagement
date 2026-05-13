import 'package:flutter/material.dart';

import '../../../core/presentation/main_app_bar_actions.dart';
import '../data/statements_api.dart';
import '../models/category_item.dart';
import '../models/statement_item.dart';
import 'statement_classification_page.dart';

class StatementsListPage extends StatefulWidget {
  const StatementsListPage({super.key});

  @override
  State<StatementsListPage> createState() => _StatementsListPageState();
}

class _StatementsListPageState extends State<StatementsListPage> {
  final StatementsApi _api = StatementsApi();
  final DateTime _now = DateTime.now();

  late int _selectedYear;
  late int _selectedMonth;
  int? _selectedCategoryId;
  String? _selectedCardHolder;
  bool? _isUnclassified;

  bool _isLoading = false;
  String? _errorMessage;
  List<CategoryItem> _categories = <CategoryItem>[];
  List<StatementItem> _statements = <StatementItem>[];

  @override
  void initState() {
    super.initState();
    _selectedYear = _now.year;
    _selectedMonth = _now.month;
    _loadInitial();
  }

  Future<void> _loadInitial() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final categories = await _api.fetchCategories();
      final statements = await _api.fetchStatements(
        year: _selectedYear,
        month: _selectedMonth,
      );
      if (!mounted) return;
      setState(() {
        _categories = categories;
        _statements = statements;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'データ取得に失敗しました: $e';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _search() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final statements = await _api.fetchStatements(
        year: _selectedYear,
        month: _selectedMonth,
        categoryId: _selectedCategoryId,
        cardHolder: _selectedCardHolder,
        isUnclassified: _isUnclassified,
      );
      if (!mounted) return;
      setState(() {
        _statements = statements;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = '検索に失敗しました: $e';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _changeMonth(int delta) async {
    final current = DateTime(_selectedYear, _selectedMonth, 1);
    final next = DateTime(current.year, current.month + delta, 1);
    setState(() {
      _selectedYear = next.year;
      _selectedMonth = next.month;
    });
    await _search();
  }

  Future<void> _openFilterSheet() async {
    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) {
        int? categoryId = _selectedCategoryId;
        String? cardHolder = _selectedCardHolder;
        bool? isUnclassified = _isUnclassified;
        return StatefulBuilder(
          builder: (context, setSheetState) => SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('絞り込み条件', style: TextStyle(fontSize: 16)),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<int?>(
                    value: categoryId,
                    decoration: const InputDecoration(labelText: 'カテゴリ'),
                    items: [
                      const DropdownMenuItem<int?>(
                          value: null, child: Text('すべて')),
                      ..._categories.map(
                        (c) => DropdownMenuItem<int?>(
                          value: c.id,
                          child: Text(c.name),
                        ),
                      ),
                    ],
                    onChanged: (value) =>
                        setSheetState(() => categoryId = value),
                  ),
                  const SizedBox(height: 8),
                  DropdownButtonFormField<String?>(
                    value: cardHolder,
                    decoration: const InputDecoration(labelText: '名義人'),
                    items: const [
                      DropdownMenuItem<String?>(
                          value: null, child: Text('すべて')),
                      DropdownMenuItem<String?>(value: '夫', child: Text('夫')),
                      DropdownMenuItem<String?>(value: '妻', child: Text('妻')),
                      DropdownMenuItem<String?>(value: '共通', child: Text('共通')),
                    ],
                    onChanged: (value) =>
                        setSheetState(() => cardHolder = value),
                  ),
                  const SizedBox(height: 8),
                  DropdownButtonFormField<bool?>(
                    value: isUnclassified,
                    decoration: const InputDecoration(labelText: '未分類'),
                    items: const [
                      DropdownMenuItem<bool?>(value: null, child: Text('すべて')),
                      DropdownMenuItem<bool?>(
                          value: true, child: Text('未分類のみ')),
                      DropdownMenuItem<bool?>(
                          value: false, child: Text('分類済みのみ')),
                    ],
                    onChanged: (value) =>
                        setSheetState(() => isUnclassified = value),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () {
                            setSheetState(() {
                              categoryId = null;
                              cardHolder = null;
                              isUnclassified = null;
                            });
                          },
                          child: const Text('リセット'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: FilledButton(
                          onPressed: () {
                            Navigator.of(context).pop();
                            setState(() {
                              _selectedCategoryId = categoryId;
                              _selectedCardHolder = cardHolder;
                              _isUnclassified = isUnclassified;
                            });
                            _search();
                          },
                          child: const Text('適用'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  int _activeFilterCount() {
    var count = 0;
    if (_selectedCategoryId != null) count += 1;
    if (_selectedCardHolder != null) count += 1;
    if (_isUnclassified != null) count += 1;
    return count;
  }

  String _formatYmd(DateTime date) {
    final yyyy = date.year.toString().padLeft(4, '0');
    final mm = date.month.toString().padLeft(2, '0');
    final dd = date.day.toString().padLeft(2, '0');
    return '$yyyy/$mm/$dd';
  }

  String _categoryNameFromId(int? categoryId) {
    if (categoryId == null) return '未分類';
    final found = _categories.where((c) => c.id == categoryId).toList();
    if (found.isEmpty) return 'カテゴリ#$categoryId';
    return found.first.name;
  }

  String _classifiedByLabel(String? classifiedBy) {
    switch (classifiedBy) {
      case 'rule':
        return 'ルール';
      case 'ai':
        return 'AI';
      case 'manual':
        return '手動';
      default:
        return '-';
    }
  }

  String? _aiConfidenceLabel(StatementItem item) {
    if (item.classifiedBy != 'ai' || item.aiConfidence == null) {
      return null;
    }
    return 'AI信頼度: ${(item.aiConfidence! * 100).toStringAsFixed(0)}%';
  }

  Color? _statementTileColor(StatementItem item) {
    if (item.categoryId == null) {
      return Colors.amber.withValues(alpha: 0.18);
    }
    if (item.needsAiReview) {
      return Colors.red.withValues(alpha: 0.10);
    }
    return null;
  }

  Widget? _statementReviewHint(StatementItem item) {
    if (item.categoryId == null) {
      return const Text(
        '未分類のため確認が必要です',
        style: TextStyle(
          color: Colors.orange,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      );
    }
    if (item.needsAiReview) {
      return const Text(
        'AI信頼度が基準以下のため確認が必要です',
        style: TextStyle(
          color: Colors.red,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      );
    }
    return null;
  }

  Future<void> _openClassification(StatementItem item) async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => StatementClassificationPage(
          statement: item,
          categories: _categories,
        ),
      ),
    );
    if (changed == true) {
      await _search();
    }
  }

  @override
  Widget build(BuildContext context) {
    final years = List<int>.generate(5, (i) => _now.year - 2 + i);
    final months = List<int>.generate(12, (i) => i + 1);

    return Scaffold(
      appBar: AppBar(
        title: const Text('明細一覧'),
        actions: [
          ...buildMainAppBarActions(
            context,
            uploadTargetYear: _selectedYear,
            uploadTargetMonth: _selectedMonth,
          ),
          IconButton(
            tooltip: '絞り込み',
            onPressed: _openFilterSheet,
            icon: Stack(
              clipBehavior: Clip.none,
              children: [
                const Icon(Icons.filter_list),
                if (_activeFilterCount() > 0)
                  Positioned(
                    right: -6,
                    top: -6,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 5, vertical: 1),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.error,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      constraints: const BoxConstraints(minWidth: 16),
                      child: Text(
                        _activeFilterCount().toString(),
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(8, 4, 8, 4),
            child: Row(
              children: [
                IconButton(
                  visualDensity: VisualDensity.compact,
                  onPressed: _isLoading ? null : () => _changeMonth(-1),
                  icon: const Icon(Icons.chevron_left),
                ),
                Expanded(
                  child: DropdownButtonFormField<int>(
                    value: _selectedYear,
                    isDense: true,
                    decoration: const InputDecoration(
                      labelText: '年',
                      isDense: true,
                      contentPadding:
                          EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    ),
                    items: years
                        .map((year) => DropdownMenuItem(
                            value: year, child: Text(year.toString())))
                        .toList(),
                    onChanged: (value) async {
                      if (value == null) return;
                      setState(() => _selectedYear = value);
                      await _search();
                    },
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: DropdownButtonFormField<int>(
                    value: _selectedMonth,
                    isDense: true,
                    decoration: const InputDecoration(
                      labelText: '月',
                      isDense: true,
                      contentPadding:
                          EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    ),
                    items: months
                        .map((month) => DropdownMenuItem(
                              value: month,
                              child: Text(month.toString()),
                            ))
                        .toList(),
                    onChanged: (value) async {
                      if (value == null) return;
                      setState(() => _selectedMonth = value);
                      await _search();
                    },
                  ),
                ),
                IconButton(
                  visualDensity: VisualDensity.compact,
                  onPressed: _isLoading ? null : () => _changeMonth(1),
                  icon: const Icon(Icons.chevron_right),
                ),
              ],
            ),
          ),
          if (_errorMessage != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  _errorMessage!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            child: Row(
              children: [
                Text('件数: ${_statements.length}'),
                const SizedBox(width: 12),
                Text(
                  '合計: ${_statements.fold<int>(0, (sum, item) => sum + item.amount)} 円',
                ),
              ],
            ),
          ),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _statements.isEmpty
                    ? RefreshIndicator(
                        onRefresh: _search,
                        child: ListView(
                          physics: const AlwaysScrollableScrollPhysics(),
                          children: [
                            const SizedBox(height: 80),
                            Center(
                              child: Padding(
                                padding:
                                    const EdgeInsets.symmetric(horizontal: 24),
                                child: Column(
                                  children: [
                                    Icon(
                                      Icons.inbox_outlined,
                                      size: 64,
                                      color:
                                          Theme.of(context).colorScheme.outline,
                                    ),
                                    const SizedBox(height: 12),
                                    Text(
                                      _activeFilterCount() > 0
                                          ? '条件に該当する明細はありません'
                                          : '$_selectedYear年$_selectedMonth月の明細はまだアップロードされていません',
                                      textAlign: TextAlign.center,
                                      style:
                                          Theme.of(context).textTheme.bodyLarge,
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),
                      )
                    : RefreshIndicator(
                        onRefresh: _search,
                        child: ListView.separated(
                          itemCount: _statements.length,
                          separatorBuilder: (_, __) => const Divider(height: 1),
                          itemBuilder: (context, index) {
                            final item = _statements[index];
                            final aiConfidenceLabel = _aiConfidenceLabel(item);
                            final reviewHint = _statementReviewHint(item);
                            return ListTile(
                              tileColor: _statementTileColor(item),
                              onTap: () => _openClassification(item),
                              title: Text(item.shopName),
                              subtitle: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    [
                                      _formatYmd(item.usedAt),
                                      item.cardHolder ?? '-',
                                      _categoryNameFromId(item.categoryId),
                                      _classifiedByLabel(item.classifiedBy),
                                      if (aiConfidenceLabel != null)
                                        aiConfidenceLabel,
                                    ].join(' / '),
                                  ),
                                  if (reviewHint != null) reviewHint,
                                ],
                              ),
                              trailing: Text('${item.amount} 円'),
                            );
                          },
                        ),
                      ),
          ),
        ],
      ),
    );
  }
}
