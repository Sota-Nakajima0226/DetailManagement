import 'package:flutter/material.dart';

import '../../statements/data/statements_api.dart';

class FixedExpensesPage extends StatefulWidget {
  const FixedExpensesPage({super.key});

  @override
  State<FixedExpensesPage> createState() => _FixedExpensesPageState();
}

class _FixedExpensesPageState extends State<FixedExpensesPage> {
  final StatementsApi _api = StatementsApi();
  List<Map<String, dynamic>> _items = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> _categories = <Map<String, dynamic>>[];
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final categories = await _api.fetchCategoriesRaw();
      final items = await _api.fetchFixedExpenses();
      if (!mounted) return;
      setState(() {
        _categories = categories;
        _items = items;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _categoryName(int? id) {
    if (id == null) return '未設定';
    final found = _categories.where((c) => c['id'] == id);
    if (found.isEmpty) return 'カテゴリ#$id';
    return found.first['name'].toString();
  }

  Future<void> _openForm({Map<String, dynamic>? item}) async {
    final name = TextEditingController(text: item?['name']?.toString() ?? '');
    final amount = TextEditingController(text: (item?['amount'] ?? '').toString());
    final billingDay = TextEditingController(text: (item?['billing_day'] ?? '').toString());
    final validFrom = TextEditingController(
      text: (item?['valid_from'] ?? DateTime.now().toIso8601String().split('T').first).toString(),
    );
    final validUntil = TextEditingController(text: (item?['valid_until'] ?? '').toString());
    String cardHolder = (item?['card_holder'] ?? '共通').toString();
    int? categoryId = item?['category_id'] as int?;
    bool isActive = item?['is_active'] as bool? ?? true;

    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(item == null ? '固定費追加' : '固定費編集'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(controller: name, decoration: const InputDecoration(labelText: '名称')),
                TextField(
                  controller: amount,
                  decoration: const InputDecoration(labelText: '金額'),
                  keyboardType: TextInputType.number,
                ),
                DropdownButtonFormField<int>(
                  value: categoryId,
                  items: _categories
                      .map((c) => DropdownMenuItem<int>(
                            value: c['id'] as int,
                            child: Text(c['name'].toString()),
                          ))
                      .toList(),
                  onChanged: (v) => setDialogState(() => categoryId = v),
                  decoration: const InputDecoration(labelText: 'カテゴリ'),
                ),
                TextField(
                  controller: billingDay,
                  decoration: const InputDecoration(labelText: '引落日'),
                  keyboardType: TextInputType.number,
                ),
                DropdownButtonFormField<String>(
                  value: cardHolder,
                  items: const [
                    DropdownMenuItem(value: '共通', child: Text('共通')),
                    DropdownMenuItem(value: '夫', child: Text('夫')),
                    DropdownMenuItem(value: '妻', child: Text('妻')),
                  ],
                  onChanged: (v) => setDialogState(() => cardHolder = v ?? '共通'),
                  decoration: const InputDecoration(labelText: '名義人'),
                ),
                TextField(
                  controller: validFrom,
                  decoration: const InputDecoration(labelText: '適用開始日 (YYYY-MM-DD)'),
                ),
                TextField(
                  controller: validUntil,
                  decoration: const InputDecoration(labelText: '適用終了日 (任意)'),
                ),
                CheckboxListTile(
                  value: isActive,
                  onChanged: (v) => setDialogState(() => isActive = v ?? true),
                  title: const Text('有効'),
                  contentPadding: EdgeInsets.zero,
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('キャンセル')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('保存')),
          ],
        ),
      ),
    );
    if (ok != true) return;

    final parsedAmount = int.tryParse(amount.text.trim());
    final parsedDay = billingDay.text.trim().isEmpty ? null : int.tryParse(billingDay.text.trim());
    final from = DateTime.tryParse(validFrom.text.trim());
    final until = validUntil.text.trim().isEmpty ? null : DateTime.tryParse(validUntil.text.trim());
    if (name.text.trim().isEmpty ||
        parsedAmount == null ||
        parsedAmount <= 0 ||
        categoryId == null ||
        from == null ||
        (validUntil.text.trim().isNotEmpty && until == null) ||
        (until != null && from.isAfter(until))) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('入力内容を確認してください')),
      );
      return;
    }

    final payload = <String, dynamic>{
      'name': name.text.trim(),
      'amount': parsedAmount,
      'category_id': categoryId,
      'billing_day': parsedDay,
      'card_holder': cardHolder,
      'is_active': isActive,
      'valid_from': validFrom.text.trim(),
      'valid_until': validUntil.text.trim().isEmpty ? null : validUntil.text.trim(),
    };
    if (item == null) {
      await _api.createFixedExpense(payload);
    } else {
      await _api.updateFixedExpense(item['id'] as int, payload);
    }
    await _load();
  }

  Future<void> _disable(int id) async {
    await _api.disableFixedExpense(id);
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('固定費管理')),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _openForm(),
        child: const Icon(Icons.add),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('エラー: $_error'))
              : ListView.builder(
                  itemCount: _items.length,
                  itemBuilder: (context, index) {
                    final item = _items[index];
                    return ListTile(
                      title: Text('${item['name']} (${item['amount']}円)'),
                      subtitle: Text(
                        'カテゴリ: ${_categoryName(item['category_id'] as int?)} / 期間: ${item['valid_from']} - ${item['valid_until'] ?? '継続'} / 有効: ${item['is_active']}',
                      ),
                      trailing: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          IconButton(
                            onPressed: () => _openForm(item: item),
                            icon: const Icon(Icons.edit),
                          ),
                          IconButton(
                            onPressed: () => _disable(item['id'] as int),
                            icon: const Icon(Icons.block),
                          ),
                        ],
                      ),
                    );
                  },
                ),
    );
  }
}
