import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_providers.dart';
import '../../statements/data/statements_api.dart';
import '../../statements/models/card_issuer.dart';
import '../../statements/presentation/upload_status_badge.dart';
import '../models/statement_upload_batch_result.dart';
import '../models/upload_file_payload.dart';
import '../models/upload_status.dart';

class _SelectedCsv {
  _SelectedCsv({
    required this.fileName,
    required this.bytes,
  });

  final String fileName;
  final Uint8List bytes;
  String? issuerCode;
  String? detectedDisplayName;
  bool detecting = true;
}

class UploadPage extends ConsumerStatefulWidget {
  const UploadPage({
    super.key,
    this.initialYear,
    this.initialMonth,
  });

  final int? initialYear;
  final int? initialMonth;

  @override
  ConsumerState<UploadPage> createState() => _UploadPageState();
}

class _UploadPageState extends ConsumerState<UploadPage> {
  late final StatementsApi _api;
  final DateTime _now = DateTime.now();

  late int _selectedYear;
  late int _selectedMonth;
  List<CardIssuer> _issuers = <CardIssuer>[];
  Future<void>? _issuersFuture;
  UploadStatus? _uploadStatus;
  bool _statusLoading = false;
  String? _statusError;
  int _statusGeneration = 0;
  int _pickGeneration = 0;

  List<_SelectedCsv> _files = <_SelectedCsv>[];
  StatementUploadBatchResult? _result;
  String? _errorMessage;
  bool _isUploading = false;

  @override
  void initState() {
    super.initState();
    _api = ref.read(statementsApiProvider);
    final iy = widget.initialYear;
    final im = widget.initialMonth;
    if (iy != null && im != null) {
      _selectedYear = iy;
      _selectedMonth = im;
    } else {
      _selectedYear = _now.year;
      _selectedMonth = _now.month;
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _ensureIssuers();
      _loadStatus();
    });
  }

  List<CardIssuer> get _activeIssuers {
    return _issuers.where((issuer) => issuer.isActive).toList();
  }

  bool get _isDetecting => _files.any((file) => file.detecting);

  bool get _hasUnresolvedIssuer => _files.any((file) => file.issuerCode == null);

  bool get _canUpload {
    if (_isUploading || _isDetecting || _files.isEmpty) return false;
    if (_hasUnresolvedIssuer) return false;
    if (_duplicateCodes().isNotEmpty) return false;
    return true;
  }

  Future<void> _ensureIssuers() {
    final existing = _issuersFuture;
    if (existing != null) return existing;
    final future = _loadIssuers();
    _issuersFuture = future;
    return future.catchError((Object _) {
      if (identical(_issuersFuture, future)) {
        _issuersFuture = null;
      }
    });
  }

  Future<void> _loadIssuers() async {
    try {
      final issuers = await _api.fetchCardIssuers();
      if (!mounted) return;
      setState(() => _issuers = issuers);
    } catch (e) {
      if (!mounted) return;
      setState(() => _errorMessage = '発行会社一覧の取得に失敗しました: $e');
      rethrow;
    }
  }

  Future<void> _loadStatus() async {
    final generation = ++_statusGeneration;
    final year = _selectedYear;
    final month = _selectedMonth;
    setState(() {
      _statusLoading = true;
      _statusError = null;
      _uploadStatus = null;
    });
    try {
      final status = await _api.fetchUploadStatus(year: year, month: month);
      if (!mounted || generation != _statusGeneration) return;
      setState(() => _uploadStatus = status);
    } catch (e) {
      if (!mounted || generation != _statusGeneration) return;
      setState(() => _statusError = '取込状況の取得に失敗しました: $e');
    } finally {
      if (mounted && generation == _statusGeneration) {
        setState(() => _statusLoading = false);
      }
    }
  }

  void _changeYear(int year) {
    setState(() => _selectedYear = year);
    _loadStatus();
  }

  void _changeMonth(int month) {
    setState(() => _selectedMonth = month);
    _loadStatus();
  }

  String _displayName(String code) {
    for (final issuer in _issuers) {
      if (issuer.code == code) return issuer.displayName;
    }
    final status = _uploadStatus;
    if (status != null) {
      for (final issuer in status.expectedIssuers) {
        if (issuer.code == code) return issuer.displayName;
      }
      for (final issuer in status.uploaded) {
        if (issuer.code == code) return issuer.displayName;
      }
      for (final issuer in status.missing) {
        if (issuer.code == code) return issuer.displayName;
      }
    }
    return code;
  }

  Set<String> _duplicateCodes() {
    final counts = <String, int>{};
    for (final file in _files) {
      final code = file.issuerCode;
      if (code == null) continue;
      counts[code] = (counts[code] ?? 0) + 1;
    }
    return counts.entries.where((entry) => entry.value > 1).map((entry) => entry.key).toSet();
  }

  String? _duplicateMessage() {
    final codes = _duplicateCodes();
    if (codes.isEmpty) return null;
    final names = codes.map(_displayName).join('、');
    return '同じ発行会社（$names）のファイルが複数あります。1社につき1ファイルにしてください。';
  }

  Future<void> _pickFiles() async {
    final picked = await FilePicker.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['csv'],
      allowMultiple: true,
      withData: true,
    );
    if (picked == null || picked.files.isEmpty || !mounted) return;

    final selected = <_SelectedCsv>[];
    for (final file in picked.files) {
      final name = file.name;
      final bytes = file.bytes;
      if (bytes == null || name.isEmpty || !name.toLowerCase().endsWith('.csv')) {
        setState(() => _errorMessage = 'CSV ファイルを選択してください。');
        return;
      }
      selected.add(_SelectedCsv(fileName: name, bytes: bytes));
    }

    final generation = ++_pickGeneration;
    setState(() {
      _files = selected;
      _errorMessage = null;
      _result = null;
    });
    await Future.wait(selected.map((file) => _detectFile(file, generation)));
  }

  Future<void> _detectFile(_SelectedCsv file, int generation) async {
    try {
      final result = await _api.detectIssuer(
        fileName: file.fileName,
        fileBytes: file.bytes,
      );
      try {
        await _ensureIssuers();
      } catch (_) {
        // 一覧が取れなくても判定名は表示し、コードは未確定のままにする。
      }
      if (!mounted || generation != _pickGeneration || !_files.contains(file)) return;
      final code = result.detectedCode;
      final active = code != null && _activeIssuers.any((issuer) => issuer.code == code);
      setState(() {
        file.detecting = false;
        file.issuerCode = active ? code : null;
        file.detectedDisplayName = result.detectedDisplayName;
      });
    } catch (e) {
      if (!mounted || generation != _pickGeneration || !_files.contains(file)) return;
      setState(() {
        file.detecting = false;
        file.issuerCode = null;
        _errorMessage = '発行会社の判定に失敗しました: $e';
      });
    }
  }

  void _removeFile(_SelectedCsv file) {
    setState(() => _files.remove(file));
  }

  Future<void> _upload() async {
    if (!_canUpload) return;
    setState(() {
      _isUploading = true;
      _errorMessage = null;
    });
    try {
      await _loadStatus();
      if (!mounted) return;
      final status = _uploadStatus;
      if (status == null) {
        setState(() {
          _errorMessage = _statusError ?? '取込状況を確認できませんでした。';
        });
        return;
      }

      final selectedCodes = _files.map((file) => file.issuerCode).whereType<String>().toSet();
      final replacing = status.uploaded.where((item) => selectedCodes.contains(item.code)).toList();
      if (replacing.isNotEmpty) {
        final names = replacing.map((item) => item.displayName).join('、');
        final shouldReplace = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('置換の確認'),
            content: Text('$_selectedYear年$_selectedMonth月の$namesは既に取り込まれています。上書きしますか？'),
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
        if (shouldReplace != true || !mounted) return;
      }

      final result = await _api.uploadStatements(
        files: [
          for (final file in _files)
            UploadFilePayload(fileName: file.fileName, bytes: file.bytes),
        ],
        cardIssuerCodes: [
          for (final file in _files) file.issuerCode!,
        ],
        year: _selectedYear,
        month: _selectedMonth,
      );
      if (!mounted) return;
      setState(() {
        _result = result;
        _files = [];
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('アップロード完了')),
      );
      await _loadStatus();
    } catch (e) {
      if (!mounted) return;
      setState(() => _errorMessage = 'アップロードに失敗しました: $e');
    } finally {
      if (mounted) {
        setState(() => _isUploading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final years = List<int>.generate(5, (i) => _now.year - 2 + i);
    final months = List<int>.generate(12, (i) => i + 1);
    final duplicateMessage = _duplicateMessage();
    final scheme = Theme.of(context).colorScheme;

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
                  const Text('ファイル選択（CSV）'),
                  const SizedBox(height: 8),
                  OutlinedButton(
                    onPressed: _isUploading ? null : _pickFiles,
                    child: const Text('ファイルを選択'),
                  ),
                  const SizedBox(height: 8),
                  if (_files.isEmpty)
                    const Text('未選択')
                  else
                    for (final file in _files) ...[
                      const Divider(height: 16),
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(file.fileName),
                                const SizedBox(height: 4),
                                if (file.detecting)
                                  const Text('判定中...')
                                else
                                  Text(
                                    file.detectedDisplayName == null
                                        ? '自動判定できませんでした'
                                        : '自動判定: ${file.detectedDisplayName}',
                                  ),
                                const SizedBox(height: 8),
                                DropdownButtonFormField<String?>(
                                  value: file.issuerCode,
                                  decoration: const InputDecoration(
                                    labelText: 'カード発行会社',
                                    isDense: true,
                                  ),
                                  items: [
                                    const DropdownMenuItem<String?>(
                                      value: null,
                                      child: Text('発行会社を選択'),
                                    ),
                                    for (final issuer in _activeIssuers)
                                      DropdownMenuItem<String?>(
                                        value: issuer.code,
                                        child: Text(issuer.displayName),
                                      ),
                                  ],
                                  onChanged: _isUploading || file.detecting
                                      ? null
                                      : (value) {
                                          setState(() => file.issuerCode = value);
                                        },
                                ),
                              ],
                            ),
                          ),
                          IconButton(
                            tooltip: '外す',
                            onPressed: _isUploading ? null : () => _removeFile(file),
                            icon: const Icon(Icons.close),
                          ),
                        ],
                      ),
                    ],
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
                  Row(
                    children: [
                      Expanded(
                        child: DropdownButtonFormField<int>(
                          value: _selectedYear,
                          decoration: const InputDecoration(labelText: '対象年'),
                          items: years
                              .map(
                                (year) => DropdownMenuItem(
                                  value: year,
                                  child: Text(year.toString()),
                                ),
                              )
                              .toList(),
                          onChanged: _isUploading
                              ? null
                              : (value) {
                                  if (value == null) return;
                                  _changeYear(value);
                                },
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: DropdownButtonFormField<int>(
                          value: _selectedMonth,
                          decoration: const InputDecoration(labelText: '対象月'),
                          items: months
                              .map(
                                (month) => DropdownMenuItem(
                                  value: month,
                                  child: Text(month.toString()),
                                ),
                              )
                              .toList(),
                          onChanged: _isUploading
                              ? null
                              : (value) {
                                  if (value == null) return;
                                  _changeMonth(value);
                                },
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  UploadStatusBadge(
                    status: _uploadStatus,
                    isLoading: _statusLoading,
                  ),
                  if (_statusError != null) ...[
                    const SizedBox(height: 8),
                    Text(_statusError!, style: TextStyle(color: scheme.error)),
                  ],
                ],
              ),
            ),
          ),
          if (_files.isNotEmpty && !_isDetecting && _hasUnresolvedIssuer) ...[
            const SizedBox(height: 12),
            Text(
              '発行会社が未確定のファイルがあります。選択してからアップロードしてください。',
              style: TextStyle(color: scheme.error),
            ),
          ],
          if (duplicateMessage != null) ...[
            const SizedBox(height: 12),
            Text(duplicateMessage, style: TextStyle(color: scheme.error)),
          ],
          if (_errorMessage != null) ...[
            const SizedBox(height: 12),
            Text(_errorMessage!, style: TextStyle(color: scheme.error)),
          ],
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _canUpload ? _upload : null,
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
                    for (final item in _result!.results) ...[
                      Text(_displayName(item.cardIssuerCode)),
                      Text('登録件数: ${item.insertedCount}'),
                      Text('未分類件数: ${item.unclassifiedCount}'),
                      Text('エラー件数: ${item.errorCount}'),
                      const SizedBox(height: 8),
                    ],
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}
