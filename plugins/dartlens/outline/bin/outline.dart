import 'dart:convert';
import 'dart:io';

import 'package:analyzer/dart/analysis/features.dart';
import 'package:analyzer/dart/analysis/utilities.dart';
import 'package:analyzer/dart/ast/ast.dart';
import 'package:analyzer/dart/ast/token.dart';
import 'package:analyzer/dart/ast/visitor.dart';
import 'package:analyzer/source/line_info.dart';

typedef Json = Map<String, Object?>;

const testCalls = {
  'group',
  'test',
  'testWidgets',
  'blocTest',
  'testGoldens',
  'goldenTest',
  'patrolTest',
  'patrolWidgetTest',
  'setUp',
  'setUpAll',
  'tearDown',
  'tearDownAll',
};
final testLike = RegExp(r'^(test[A-Z]\w*|\w+Test|group[A-Z]\w*)$');
final spaces = RegExp(r'\s+');
final docPrefix = RegExp(r'^\s*(///?|/\*\*|\*/|\*)\s?');

class Outliner {
  Outliner(this.text, this.lineInfo);

  final String text;
  final LineInfo lineInfo;

  int line(int offset) => lineInfo.getLocation(offset).lineNumber;

  String clip(String value, [int max = 160]) {
    final flat = value.replaceAll(spaces, ' ').trim();
    return flat.length > max ? '${flat.substring(0, max - 1)}…' : flat;
  }

  String source(int from, int to) => clip(text.substring(from, to < from ? from : to));

  int head(AstNode node) => node is AnnotatedNode ? node.firstTokenAfterCommentAndMetadata.offset : node.offset;

  String? doc(AstNode node) {
    final comment = node is AnnotatedNode ? node.documentationComment : null;
    if (comment == null) return null;
    final raw = comment.tokens.map((t) => t.lexeme.split('\n').map((l) => l.replaceFirst(docPrefix, '')).join(' ')).join(' ');
    final flat = clip(raw, 400);
    final stop = flat.indexOf('. ');
    return clip(stop > 0 ? flat.substring(0, stop + 1) : flat, 120);
  }

  String bodySuffix(FunctionBody body) {
    final keyword = body.keyword?.lexeme;
    final star = body.star != null ? '*' : '';
    final arrow = body is ExpressionFunctionBody ? ' =>' : '';
    return '${keyword != null ? ' $keyword$star' : ''}$arrow';
  }

  String variables(VariableDeclarationList list, {bool isStatic = false}) => clip([
        if (isStatic) 'static',
        if (list.lateKeyword != null) 'late',
        if (list.keyword != null) list.keyword!.lexeme,
        if (list.type != null) list.type!.toSource(),
        list.variables.map((v) => v.name.lexeme).join(', '),
      ].join(' '));

  Json entry(String kind, String name, AstNode node, String signature, {Token? nameToken, List<Json>? children}) {
    final documentation = doc(node);
    return {
      'kind': kind,
      'name': name,
      'signature': signature,
      'start': line(node.offset),
      'end': line(node.end),
      'line': line(nameToken?.offset ?? head(node)),
      if (documentation != null) 'doc': documentation,
      'children': children ?? <Json>[],
    };
  }

  List<Json> members(NodeList<ClassMember> nodes) {
    final out = <Json>[];
    for (final member in nodes) {
      if (member is MethodDeclaration) {
        final kind = member.isGetter
            ? 'getter'
            : member.isSetter
                ? 'setter'
                : member.isOperator
                    ? 'operator'
                    : 'method';
        out.add(entry(kind, member.name.lexeme, member, source(head(member), member.body.offset) + bodySuffix(member.body),
            nameToken: member.name));
      } else if (member is ConstructorDeclaration) {
        out.add(entry('constructor', member.name?.lexeme ?? '', member, source(head(member), member.parameters.end),
            nameToken: member.name));
      } else if (member is FieldDeclaration) {
        out.add(entry('field', member.fields.variables.map((v) => v.name.lexeme).join(', '), member,
            variables(member.fields, isStatic: member.isStatic)));
      } else {
        out.add(entry(member.runtimeType.toString(), '', member, source(head(member), member.end)));
      }
    }
    return out;
  }

  Json declaration(CompilationUnitMember d) {
    if (d is ClassDeclaration) {
      return entry('class', d.namePart.typeName.lexeme, d, source(head(d), d.body.offset),
          nameToken: d.namePart.typeName, children: members(d.body.members));
    }
    if (d is MixinDeclaration) {
      return entry('mixin', d.name.lexeme, d, source(head(d), d.body.offset), nameToken: d.name, children: members(d.body.members));
    }
    if (d is ExtensionTypeDeclaration) {
      final name = d.primaryConstructor.typeName;
      return entry('extension type', name.lexeme, d, source(head(d), d.body.offset),
          nameToken: name, children: members(d.body.members));
    }
    if (d is ExtensionDeclaration) {
      return entry('extension', d.name?.lexeme ?? '<unnamed>', d, source(head(d), d.body.offset),
          nameToken: d.name, children: members(d.body.members));
    }
    if (d is EnumDeclaration) {
      final constants = d.body.constants;
      final children = <Json>[
        if (constants.isNotEmpty)
          {
            'kind': 'constants',
            'name': '${constants.length} values',
            'signature': clip(constants.map((c) => c.name.lexeme).join(', '), 120),
            'start': line(constants.first.offset),
            'end': line(constants.last.end),
            'line': line(constants.first.offset),
            'children': <Json>[],
          },
        ...members(d.body.members),
      ];
      return entry('enum', d.namePart.typeName.lexeme, d, '${source(head(d), d.body.offset)} (${constants.length} values)',
          nameToken: d.namePart.typeName, children: children);
    }
    if (d is TypeAlias) {
      return entry('typedef', d.name.lexeme, d, source(head(d), d.semicolon.offset), nameToken: d.name);
    }
    if (d is FunctionDeclaration) {
      final body = d.functionExpression.body;
      final kind = d.isGetter
          ? 'getter'
          : d.isSetter
              ? 'setter'
              : 'function';
      return entry(kind, d.name.lexeme, d, source(head(d), body.offset) + bodySuffix(body), nameToken: d.name);
    }
    if (d is TopLevelVariableDeclaration) {
      return entry('variable', d.variables.variables.map((v) => v.name.lexeme).join(', '), d, variables(d.variables));
    }
    return entry(d.runtimeType.toString(), '', d, source(head(d), d.end));
  }
}

class TestCollector extends RecursiveAstVisitor<void> {
  TestCollector(this.outliner);

  final Outliner outliner;
  final roots = <Json>[];
  final _stack = <List<Json>>[];

  bool _isTest(String name, List<AstNode> args) {
    if (testCalls.contains(name)) return true;
    return testLike.hasMatch(name) &&
        args.isNotEmpty &&
        args.first is StringLiteral &&
        args.any((a) => a is FunctionExpression);
  }

  @override
  void visitMethodInvocation(MethodInvocation node) {
    final name = node.methodName.name;
    final args = node.argumentList.arguments;
    if (node.target != null || !_isTest(name, args)) {
      super.visitMethodInvocation(node);
      return;
    }
    var label = '';
    if (args.isNotEmpty) {
      final first = args.first;
      if (first is StringLiteral) {
        label = first.stringValue ?? first.toSource();
      } else if (first is Identifier) {
        label = first.toSource();
      }
    }
    final children = <Json>[];
    (_stack.isEmpty ? roots : _stack.last).add({
      'kind': name,
      'name': outliner.clip(label, 120),
      'start': outliner.line(node.offset),
      'end': outliner.line(node.end),
      'children': children,
    });
    _stack.add(children);
    super.visitMethodInvocation(node);
    _stack.removeLast();
  }
}

// Only \n ends a line, as for sed, wc -l and cat -n (the analyzer's LineInfo also breaks on a lone \r).
LineInfo newlineInfo(String text) {
  final starts = <int>[0];
  for (var i = text.indexOf('\n'); i >= 0; i = text.indexOf('\n', i + 1)) {
    starts.add(i + 1);
  }
  return LineInfo(starts);
}

Json outline(String path) {
  final watch = Stopwatch()..start();
  final text = utf8.decode(File(path).readAsBytesSync(), allowMalformed: true);
  final parsed = parseString(content: text, featureSet: FeatureSet.latestLanguageVersion(), throwIfDiagnostics: false);
  final lineInfo = newlineInfo(text);
  final outliner = Outliner(text, lineInfo);
  final unit = parsed.unit;
  final directives = unit.directives;
  final tests = TestCollector(outliner);
  unit.accept(tests);
  final lines = text.isEmpty ? 0 : lineInfo.lineCount - (text.endsWith('\n') ? 1 : 0);
  return {
    'lines': lines,
    'directives': directives.isEmpty
        ? null
        : [outliner.line(directives.first.offset), outliner.line(directives.last.end), directives.length],
    'decls': [for (final d in unit.declarations) outliner.declaration(d)],
    'tests': tests.roots,
    'errors': parsed.errors.length,
    'ms': watch.elapsedMilliseconds,
  };
}

void render(StringBuffer out, List<Object?> nodes, int depth, {bool tests = false}) {
  for (final raw in nodes) {
    final node = raw as Json;
    final label = tests
        ? "${node['kind']}${(node['name'] as String).isEmpty ? '' : " '${node['name']}'"}"
        : node['signature'];
    out.writeln('${'  ' * depth}${node['start']}-${node['end']} $label');
    render(out, node['children'] as List<Object?>, depth + 1, tests: tests);
  }
}

String text(String path, Json data) {
  final out = StringBuffer();
  if (data['error'] != null) {
    out.writeln('== $path : ${data['error']}');
    return out.toString();
  }
  final errors = data['errors'] as int;
  out.writeln('== $path (${data['lines']} lignes${errors > 0 ? ' · $errors erreurs de syntaxe' : ''})');
  final directives = data['directives'] as List<Object?>?;
  if (directives != null) out.writeln('${directives[0]}-${directives[1]} directives (${directives[2]})');
  render(out, data['decls'] as List<Object?>, 0);
  final tests = data['tests'] as List<Object?>;
  if (tests.isNotEmpty) {
    out.writeln('tests :');
    render(out, tests, 1, tests: true);
  }
  return out.toString();
}

void main(List<String> args) {
  var json = false;
  final paths = <String>[];
  for (final arg in args) {
    if (arg == '--json') {
      json = true;
    } else if (arg == '--stdin') {
      for (var line = stdin.readLineSync(encoding: utf8); line != null; line = stdin.readLineSync(encoding: utf8)) {
        if (line.trim().isNotEmpty) paths.add(line.trim());
      }
    } else {
      paths.add(arg);
    }
  }
  final result = <String, Json>{};
  for (final path in paths) {
    try {
      result[path] = outline(path);
    } catch (error) {
      result[path] = {'error': error.toString().split('\n').first};
    }
  }
  if (json) {
    stdout.write(jsonEncode(result));
  } else {
    result.forEach((path, data) => stdout.write(text(path, data)));
  }
  exitCode = result.values.any((d) => d['error'] != null) ? 1 : 0;
}
