import 'package:flutter/material.dart';

import '../../statements/data/statements_api.dart';

class ManualExpensesPage extends StatefulWidget {
  const ManualExpensesPage({super.key});

  @override
  State<ManualExpensesPage> createState() => _ManualExpensesPageState();
}

class _ManualExpensesPageState extends State<ManualExpensesPage> {
  final StatementsApi _api = StatementsApi();
  final DateTime _now = DateTime.now();
  late int _year;
  late int _month;
  List<Map<String, dynamic>> _items = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> _categories = <Map<String, dynamic>>[];
  bool _loading = false;
  String? _error;

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
      final categories = await _api.fetchCategoriesRaw();
      final items = await _api.fetchManualExpenses(year: _year, month: _month);
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
    final usedAt = TextEditingController(
      text: (item?['used_at'] ?? DateTime(_year, _month, 1).toIso8601String().split('T').first)
          .toString(),
    );
    final shopName = TextEditingController(text: item?['shop_name']?.toString() ?? '');
    final amount = TextEditingController(text: (item?['amount'] ?? '').toString());
    final note = TextEditingController(text: item?['note']?.toString() ?? '');
    String cardHolder = (item?['card_holder'] ?? '共通').toString();
    int? categoryId = item?['category_id'] as int?;

    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(item == null ? '手動支払い追加' : '手動支払い編集'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: usedAt,
                  decoration: const InputDecoration(labelText: '利用日 (YYYY-MM-DD)'),
                ),
                TextField(controller: shopName, decoration: const InputDecoration(labelText: '店名')),
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
                TextField(controller: note, decoration: const InputDecoration(labelText: 'メモ')),
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

    final parsedDate = DateTime.tryParse(usedAt.text.trim());
    final parsedAmount = int.tryParse(amount.text.trim());
    if (parsedDate == null || shopName.text.trim().isEmpty || parsedAmount == null || categoryId == null) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('入力内容を確認してください')),
      );
      return;
    }

    final payload = <String, dynamic>{
      'used_at': usedAt.text.trim(),
      'shop_name': shopName.text.trim(),
      'amount': parsedAmount,
      'category_id': categoryId,
      'card_holder': cardHolder,
      'year': _year,
      'month': _month,
      'note': note.text.trim().isEmpty ? null : note.text.trim(),
      'created_by': 'app',
    };
    if (item == null) {
      await _api.createManualExpense(payload);
    } else {
      await _api.updateManualExpense(item['id'] as int, payload);
    }
    await _load();
  }

  Future<void> _delete(int id) async {
    await _api.deleteManualExpense(id);
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    final years = List<int>.generate(5, (i) => _now.year - 2 + i);
    final months = List<int>.generate(12, (i) => i + 1);

    return Scaffold(
      appBar: AppBar(title: const Text('手動支払い登録')),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _openForm(),
        child: const Icon(Icons.add),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
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
                ElevatedButton(onPressed: _load, child: const Text('検索')),
              ],
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(child: Text('エラー: $_error'))
                    : ListView.builder(
                        itemCount: _items.length,
                        itemBuilder: (context, index) {
                          final item = _items[index];
                          return ListTile(
                            title: Text('${item['shop_name']} (${item['amount']}円)'),
                            subtitle: Text(
                              '${item['used_at']} / ${_categoryName(item['category_id'] as int?)} / ${item['card_holder']}',
                            ),
                            trailing: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                IconButton(
                                  onPressed: () => _openForm(item: item),
                                  icon: const Icon(Icons.edit),
                                ),
                                IconButton(
                                  onPressed: () => _delete(item['id'] as int),
                                  icon: const Icon(Icons.delete),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}
