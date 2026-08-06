import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_providers.dart';
import '../../statements/data/statements_api.dart';

class RulesPage extends ConsumerStatefulWidget {
  const RulesPage({super.key});

  @override
  ConsumerState<RulesPage> createState() => _RulesPageState();
}

class _RulesPageState extends ConsumerState<RulesPage> {
  late final StatementsApi _api;
  List<Map<String, dynamic>> _rules = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> _categories = <Map<String, dynamic>>[];
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _api = ref.read(statementsApiProvider);
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final categories = await _api.fetchCategoriesRaw();
      final rules = await _api.fetchRules();
      if (!mounted) return;
      setState(() {
        _categories = categories;
        _rules = rules;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _categoryName(int id) {
    final found = _categories.where((c) => c['id'] == id);
    if (found.isEmpty) return 'カテゴリ#$id';
    return found.first['name'].toString();
  }

  Future<void> _openForm({Map<String, dynamic>? item}) async {
    final pattern = TextEditingController(text: item?['pattern']?.toString() ?? '');
    final priority = TextEditingController(text: (item?['priority'] ?? 0).toString());
    bool isRegex = item?['is_regex'] as bool? ?? false;
    int? categoryId = item?['category_id'] as int?;

    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(item == null ? 'ルール追加' : 'ルール編集'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(controller: pattern, decoration: const InputDecoration(labelText: 'パターン')),
              TextField(
                controller: priority,
                decoration: const InputDecoration(
                  labelText: '優先度 (0以上)',
                ),
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
              CheckboxListTile(
                value: isRegex,
                onChanged: (v) => setDialogState(() => isRegex = v ?? false),
                title: const Text('正規表現'),
                contentPadding: EdgeInsets.zero,
              ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('キャンセル')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('保存')),
          ],
        ),
      ),
    );

    if (ok != true) return;
    final parsedPriority = int.tryParse(priority.text.trim());
    if (pattern.text.trim().isEmpty ||
        parsedPriority == null ||
        parsedPriority < 0 ||
        categoryId == null) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('入力内容を確認してください（優先度は0以上）')),
      );
      return;
    }

    if (item == null) {
      await _api.createRule(
        pattern: pattern.text.trim(),
        isRegex: isRegex,
        categoryId: categoryId!,
        priority: parsedPriority,
      );
    } else {
      await _api.updateRule(
        id: item['id'] as int,
        pattern: pattern.text.trim(),
        isRegex: isRegex,
        categoryId: categoryId!,
        priority: parsedPriority,
      );
    }
    await _load();
  }

  Future<void> _delete(int id) async {
    await _api.deleteRule(id);
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('分類ルール管理')),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _openForm(),
        child: const Icon(Icons.add),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text('エラー: $_error'))
              : ListView.builder(
                  itemCount: _rules.length,
                  itemBuilder: (context, index) {
                    final item = _rules[index];
                    return ListTile(
                      title: Text(item['pattern'].toString()),
                      subtitle: Text(
                        'カテゴリ: ${_categoryName(item['category_id'] as int)} / 優先度: ${item['priority']} / regex: ${item['is_regex']}',
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
    );
  }
}
