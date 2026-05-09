import 'package:flutter/material.dart';

import '../../statements/data/statements_api.dart';

class CategoriesPage extends StatefulWidget {
  const CategoriesPage({super.key});

  @override
  State<CategoriesPage> createState() => _CategoriesPageState();
}

class _CategoriesPageState extends State<CategoriesPage> {
  final StatementsApi _api = StatementsApi();
  List<Map<String, dynamic>> _items = <Map<String, dynamic>>[];
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
      final data = await _api.fetchCategoriesRaw();
      if (!mounted) return;
      setState(() => _items = data);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openForm({Map<String, dynamic>? item}) async {
    final name = TextEditingController(text: item?['name']?.toString() ?? '');
    final color = TextEditingController(text: item?['color']?.toString() ?? '#888888');
    final sortOrder =
        TextEditingController(text: (item?['sort_order'] ?? 0).toString());

    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(item == null ? 'カテゴリ追加' : 'カテゴリ編集'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: name, decoration: const InputDecoration(labelText: '名称')),
            TextField(controller: color, decoration: const InputDecoration(labelText: '色')),
            TextField(
              controller: sortOrder,
              decoration: const InputDecoration(labelText: '表示順'),
              keyboardType: TextInputType.number,
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('キャンセル')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('保存')),
        ],
      ),
    );
    if (ok != true) return;

    final parsedOrder = int.tryParse(sortOrder.text.trim());
    if (name.text.trim().isEmpty || parsedOrder == null) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('名称と表示順を正しく入力してください')),
      );
      return;
    }

    if (item == null) {
      await _api.createCategory(
        name: name.text.trim(),
        color: color.text.trim(),
        sortOrder: parsedOrder,
      );
    } else {
      await _api.updateCategory(
        id: item['id'] as int,
        name: name.text.trim(),
        color: color.text.trim(),
        sortOrder: parsedOrder,
      );
    }
    await _load();
  }

  Future<void> _delete(int id) async {
    await _api.deleteCategory(id);
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('カテゴリ管理')),
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
                      title: Text(item['name'].toString()),
                      subtitle: Text('色: ${item['color']} / 表示順: ${item['sort_order']}'),
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
