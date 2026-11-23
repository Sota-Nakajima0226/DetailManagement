import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_providers.dart';
import '../data/statements_api.dart';
import '../models/category_item.dart';
import '../models/statement_item.dart';

class StatementClassificationPage extends ConsumerStatefulWidget {
  const StatementClassificationPage({
    super.key,
    required this.statement,
    required this.categories,
  });

  final StatementItem statement;
  final List<CategoryItem> categories;

  @override
  ConsumerState<StatementClassificationPage> createState() =>
      _StatementClassificationPageState();
}

class _StatementClassificationPageState
    extends ConsumerState<StatementClassificationPage> {
  late final StatementsApi _api;
  late final TextEditingController _patternController;
  bool _isSaving = false;
  bool _addRule = false;
  bool _isRegex = false;
  bool _statementSaved = false;
  String? _errorMessage;
  int? _selectedCategoryId;

  @override
  void initState() {
    super.initState();
    _api = ref.read(statementsApiProvider);
    _selectedCategoryId = widget.statement.categoryId;
    _patternController = TextEditingController(text: widget.statement.shopName);
  }

  @override
  void dispose() {
    _patternController.dispose();
    super.dispose();
  }

  String _formatYmd(DateTime date) {
    final yyyy = date.year.toString().padLeft(4, '0');
    final mm = date.month.toString().padLeft(2, '0');
    final dd = date.day.toString().padLeft(2, '0');
    return '$yyyy/$mm/$dd';
  }

  String? _categoryName(int categoryId) {
    for (final category in widget.categories) {
      if (category.id == categoryId) return category.name;
    }
    return null;
  }

  Future<void> _saveCategoryOnly(int categoryId) async {
    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });
    try {
      await _api.updateStatementCategory(
        statementItemId: widget.statement.id,
        categoryId: categoryId,
      );
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = '保存に失敗しました: ${_apiErrorDetail(e)}';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isSaving = false;
        });
      }
    }
  }

  Future<_RuleSaveAttempt> _saveCategoryAndRule(
    String rawPattern,
    bool isRegex,
  ) async {
    final categoryId = _selectedCategoryId;
    if (categoryId == null) {
      return const _RuleSaveAttempt.stay('カテゴリを選択してください。');
    }
    final pattern = rawPattern.trim();
    if (pattern.isEmpty) {
      return const _RuleSaveAttempt.stay('支払い名を入力してください。');
    }
    try {
      await _api.validateRule(pattern: pattern, isRegex: isRegex);
    } catch (e) {
      return _RuleSaveAttempt.stay(_apiErrorDetail(e));
    }
    try {
      await _api.updateStatementCategory(
        statementItemId: widget.statement.id,
        categoryId: categoryId,
      );
    } catch (e) {
      return _RuleSaveAttempt.stay('保存に失敗しました: ${_apiErrorDetail(e)}');
    }
    _statementSaved = true;
    try {
      await _saveRule(
        pattern: pattern,
        isRegex: isRegex,
        categoryId: categoryId,
      );
    } catch (e) {
      return const _RuleSaveAttempt.pageError(
        '明細は保存しました。ルールの追加に失敗しました',
      );
    }
    return const _RuleSaveAttempt.close();
  }

  Future<void> _saveRule({
    required String pattern,
    required bool isRegex,
    required int categoryId,
  }) async {
    final rules = await _api.fetchRules();
    final priority = _nextPriority(rules);
    final matches = rules.where((rule) {
      final existing = (rule['pattern']?.toString() ?? '').trim();
      final existingRegex = rule['is_regex'] == true;
      return existing == pattern && existingRegex == isRegex;
    }).toList();
    if (matches.isEmpty) {
      await _api.createRule(
        pattern: pattern,
        isRegex: isRegex,
        categoryId: categoryId,
        priority: priority,
      );
      return;
    }
    for (final rule in matches) {
      await _api.updateRule(
        id: rule['id'] as int,
        pattern: pattern,
        isRegex: isRegex,
        categoryId: categoryId,
        priority: priority,
      );
    }
  }

  int _nextPriority(List<Map<String, dynamic>> rules) {
    if (rules.isEmpty) return 10;
    var maxPriority = 0;
    for (final rule in rules) {
      final priority = (rule['priority'] as num?)?.toInt() ?? 0;
      if (priority > maxPriority) maxPriority = priority;
    }
    return maxPriority + 10;
  }

  Future<void> _openRuleDialog() async {
    final categoryId = _selectedCategoryId;
    final categoryName = categoryId == null ? null : _categoryName(categoryId);
    if (categoryId == null || categoryName == null) {
      setState(() {
        _errorMessage = 'カテゴリを選択してください。';
      });
      return;
    }
    final result = await showDialog<_RuleDialogResult>(
      context: context,
      barrierDismissible: false,
      builder: (context) => _RuleAddDialog(
        patternController: _patternController,
        initialIsRegex: _isRegex,
        categoryName: categoryName,
        onSubmit: _saveCategoryAndRule,
      ),
    );
    if (!mounted || result == null) return;
    setState(() {
      _isRegex = result.isRegex;
      if (result.attempt != null) {
        _errorMessage = result.attempt!.pageError;
      }
    });
    if (result.attempt?.closePage == true) {
      Navigator.of(context).pop(true);
    }
  }

  Future<void> _save() async {
    final categoryId = _selectedCategoryId;
    if (categoryId == null) {
      setState(() {
        _errorMessage = 'カテゴリを選択してください。';
        _addRule = false;
      });
      return;
    }
    if (_addRule) {
      await _openRuleDialog();
      return;
    }
    await _saveCategoryOnly(categoryId);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('明細仕分け'),
        leading: BackButton(
          onPressed: () => Navigator.of(context).pop(_statementSaved),
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(widget.statement.shopName,
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    Text('利用日: ${_formatYmd(widget.statement.usedAt)}'),
                    Text('金額: ${widget.statement.amount} 円'),
                    Text('名義人: ${widget.statement.cardHolder ?? '-'}'),
                    Text('カード発行会社: ${widget.statement.cardIssuerName ?? '-'}'),
                    Text('現在カテゴリ: ${widget.statement.categoryId ?? '未分類'}'),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<int>(
              value: _selectedCategoryId,
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
                labelText: 'カテゴリ',
              ),
              items: widget.categories
                  .map(
                    (c) => DropdownMenuItem<int>(
                      value: c.id,
                      child: Text(c.name),
                    ),
                  )
                  .toList(),
              onChanged: _isSaving
                  ? null
                  : (value) {
                      setState(() {
                        _selectedCategoryId = value;
                        if (value == null) _addRule = false;
                      });
                    },
            ),
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              value: _selectedCategoryId != null && _addRule,
              title: const Text('この店名を分類ルールに追加する'),
              onChanged: _isSaving || _selectedCategoryId == null
                  ? null
                  : (value) {
                      setState(() {
                        _addRule = value ?? false;
                      });
                    },
            ),
            if (_errorMessage != null) ...[
              const SizedBox(height: 12),
              Text(
                _errorMessage!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
            const Spacer(),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _isSaving ? null : _save,
                child: _isSaving
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('保存'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

String _apiErrorDetail(Object error) {
  if (error is DioException) {
    final data = error.response?.data;
    if (data is Map && data['detail'] != null) {
      return data['detail'].toString();
    }
  }
  return '$error';
}

class _RuleSaveAttempt {
  const _RuleSaveAttempt.stay(this.dialogError)
      : pageError = null,
        closePage = false;
  const _RuleSaveAttempt.pageError(this.pageError)
      : dialogError = null,
        closePage = false;
  const _RuleSaveAttempt.close()
      : dialogError = null,
        pageError = null,
        closePage = true;

  final String? dialogError;
  final String? pageError;
  final bool closePage;
}

class _RuleDialogResult {
  const _RuleDialogResult({required this.isRegex, this.attempt});

  final bool isRegex;
  final _RuleSaveAttempt? attempt;
}

class _RuleAddDialog extends StatefulWidget {
  const _RuleAddDialog({
    required this.patternController,
    required this.initialIsRegex,
    required this.categoryName,
    required this.onSubmit,
  });

  final TextEditingController patternController;
  final bool initialIsRegex;
  final String categoryName;
  final Future<_RuleSaveAttempt> Function(String pattern, bool isRegex) onSubmit;

  @override
  State<_RuleAddDialog> createState() => _RuleAddDialogState();
}

class _RuleAddDialogState extends State<_RuleAddDialog> {
  late bool _isRegex;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _isRegex = widget.initialIsRegex;
  }

  Future<void> _submit() async {
    setState(() {
      _saving = true;
      _error = null;
    });
    final attempt = await widget.onSubmit(widget.patternController.text, _isRegex);
    if (!mounted) return;
    if (attempt.closePage || attempt.pageError != null) {
      Navigator.of(context).pop(
        _RuleDialogResult(isRegex: _isRegex, attempt: attempt),
      );
      return;
    }
    setState(() {
      _saving = false;
      _error = attempt.dialogError;
    });
  }

  void _back() {
    Navigator.of(context).pop(_RuleDialogResult(isRegex: _isRegex));
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('分類ルールに追加'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextField(
            controller: widget.patternController,
            enabled: !_saving,
            decoration: InputDecoration(
              labelText: '支払い名',
              helperText: _isRegex ? '正規表現としてマッチ' : 'この文字を含む店名',
            ),
          ),
          CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            value: _isRegex,
            title: const Text('正規表現'),
            onChanged: _saving
                ? null
                : (value) {
                    setState(() {
                      _isRegex = value ?? false;
                    });
                  },
          ),
          Text('分類先: ${widget.categoryName}'),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
        ],
      ),
      actions: [
        TextButton(
          onPressed: _saving ? null : _back,
          child: const Text('戻る'),
        ),
        FilledButton(
          onPressed: _saving ? null : _submit,
          child: _saving
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('追加して保存'),
        ),
      ],
    );
  }
}
