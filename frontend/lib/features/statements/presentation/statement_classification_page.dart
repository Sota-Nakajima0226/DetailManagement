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
  bool _isSaving = false;
  String? _errorMessage;
  int? _selectedCategoryId;

  @override
  void initState() {
    super.initState();
    _api = ref.read(statementsApiProvider);
    _selectedCategoryId = widget.statement.categoryId;
  }

  String _formatYmd(DateTime date) {
    final yyyy = date.year.toString().padLeft(4, '0');
    final mm = date.month.toString().padLeft(2, '0');
    final dd = date.day.toString().padLeft(2, '0');
    return '$yyyy/$mm/$dd';
  }

  Future<void> _save() async {
    final categoryId = _selectedCategoryId;
    if (categoryId == null) {
      setState(() {
        _errorMessage = 'カテゴリを選択してください。';
      });
      return;
    }

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
        _errorMessage = '保存に失敗しました: $e';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isSaving = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('明細仕分け')),
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
