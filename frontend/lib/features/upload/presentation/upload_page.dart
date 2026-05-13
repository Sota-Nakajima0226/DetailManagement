import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../../statements/data/statements_api.dart';
import '../models/upload_result.dart';

class UploadPage extends StatefulWidget {
  const UploadPage({
    super.key,
    this.initialYear,
    this.initialMonth,
  });

  final int? initialYear;
  final int? initialMonth;

  @override
  State<UploadPage> createState() => _UploadPageState();
}

class _UploadPageState extends State<UploadPage> {
  final StatementsApi _api = StatementsApi();
  final DateTime _now = DateTime.now();

  String? _fileName;
  Uint8List? _fileBytes;
  late int _selectedYear;
  late int _selectedMonth;
  UploadResult? _result;
  String? _errorMessage;
  bool _isUploading = false;

  @override
  void initState() {
    super.initState();
    final iy = widget.initialYear;
    final im = widget.initialMonth;
    if (iy != null && im != null) {
      _selectedYear = iy;
      _selectedMonth = im;
    } else {
      _selectedYear = _now.year;
      _selectedMonth = _now.month;
    }
  }

  bool _isAllowedExtension(String fileName) {
    final lower = fileName.toLowerCase();
    return lower.endsWith('.csv') || lower.endsWith('.pdf');
  }

  Future<void> _pickFile() async {
    final picked = await FilePicker.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['csv', 'pdf'],
      withData: true,
    );
    if (picked == null || picked.files.isEmpty) {
      return;
    }
    final file = picked.files.first;
    if (file.bytes == null || file.name.isEmpty) {
      setState(() {
        _errorMessage = 'ファイルの取得に失敗しました。';
      });
      return;
    }
    setState(() {
      _fileName = file.name;
      _fileBytes = file.bytes!;
      _errorMessage = null;
      _result = null;
    });
  }

  Future<void> _upload() async {
    final fileName = _fileName;
    final fileBytes = _fileBytes;
    if (fileName == null || fileBytes == null) {
      setState(() {
        _errorMessage = 'ファイルを選択してください。';
      });
      return;
    }
    if (!_isAllowedExtension(fileName)) {
      setState(() {
        _errorMessage = 'CSV または PDF ファイルを選択してください。';
      });
      return;
    }

    final hasExisting = await _api.hasStatementsInMonth(
      year: _selectedYear,
      month: _selectedMonth,
    );
    if (hasExisting && mounted) {
      final shouldReplace = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('重複アップロード確認'),
          content: Text('$_selectedYear年$_selectedMonth月の明細は既に存在します。上書きしますか？'),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('キャンセル'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('上書きする'),
            ),
          ],
        ),
      );
      if (shouldReplace != true) {
        return;
      }
    }

    setState(() {
      _isUploading = true;
      _errorMessage = null;
      _result = null;
    });
    try {
      final result = await _api.uploadStatement(
        fileName: fileName,
        fileBytes: fileBytes,
        year: _selectedYear,
        month: _selectedMonth,
      );
      if (!mounted) return;
      setState(() {
        _result = result;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('アップロード完了')),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'アップロードに失敗しました: $e';
      });
    } finally {
      if (mounted) {
        setState(() {
          _isUploading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final years = List<int>.generate(5, (i) => _now.year - 2 + i);
    final months = List<int>.generate(12, (i) => i + 1);

    return Scaffold(
      appBar: AppBar(title: const Text('明細アップロード')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('ファイル選択（CSV/PDF）'),
                  const SizedBox(height: 8),
                  OutlinedButton(
                    onPressed: _isUploading ? null : _pickFile,
                    child: const Text('ファイルを選択'),
                  ),
                  const SizedBox(height: 8),
                  Text(_fileName ?? '未選択'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Expanded(
                    child: DropdownButtonFormField<int>(
                      value: _selectedYear,
                      decoration: const InputDecoration(labelText: '対象年'),
                      items: years
                          .map((year) => DropdownMenuItem(
                                value: year,
                                child: Text(year.toString()),
                              ))
                          .toList(),
                      onChanged: _isUploading
                          ? null
                          : (value) {
                              if (value == null) return;
                              setState(() => _selectedYear = value);
                            },
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: DropdownButtonFormField<int>(
                      value: _selectedMonth,
                      decoration: const InputDecoration(labelText: '対象月'),
                      items: months
                          .map((month) => DropdownMenuItem(
                                value: month,
                                child: Text(month.toString()),
                              ))
                          .toList(),
                      onChanged: _isUploading
                          ? null
                          : (value) {
                              if (value == null) return;
                              setState(() => _selectedMonth = value);
                            },
                    ),
                  ),
                ],
              ),
            ),
          ),
          if (_errorMessage != null) ...[
            const SizedBox(height: 12),
            Text(
              _errorMessage!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _isUploading ? null : _upload,
            child: _isUploading
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('アップロード実行'),
          ),
          const SizedBox(height: 16),
          if (_result != null)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('取込結果'),
                    const SizedBox(height: 8),
                    Text('登録件数: ${_result!.insertedCount}'),
                    Text('未分類件数: ${_result!.unclassifiedCount}'),
                    Text('エラー件数: ${_result!.errorCount}'),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}
