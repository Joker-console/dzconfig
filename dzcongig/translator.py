#!/usr/bin/env python3
# coding: utf-8

import argparse
import sys

# --------- Лексер ---------

class TokenKind:
    IDENT = "IDENT"
    HEX = "HEX"
    LBRACE = "{"
    RBRACE = "}"
    SEMI = ";"
    EQUAL = "="
    LPAREN = "("
    RPAREN = ")"
    COMMA = ","
    KW_ARRAY = "array"
    KW_VAR = "var"
    QMARK = "?"
    LBRACKET = "["
    RBRACKET = "]"
    EOF = "EOF"

class Token:
    def __init__(self, kind, value, line, col):
        self.kind = kind
        self.value = value
        self.line = line
        self.col = col

class LexerError(Exception):
    pass

class Lexer:
    def __init__(self, text):
        self.text = text
        self.i = 0
        self.line = 1
        self.col = 1

    def peek(self, n=1):
        pos = self.i + n - 1
        if pos >= len(self.text):
            return ""
        return self.text[pos]

    def advance(self, n=1):
        for _ in range(n):
            if self.i >= len(self.text):
                return
            ch = self.text[self.i]
            self.i += 1
            if ch == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1

    def skip_ws(self):
        while True:
            ch = self.peek()
            if ch and ch.isspace():
                self.advance()
            else:
                break

    def lex_ident_or_kw(self):
        start_line, start_col = self.line, self.col
        s = []
        ch = self.peek()
        if not ch or not ch.isalpha():
            raise LexerError(f"Ожидалось имя на позиции {self.line}:{self.col}")
        while True:
            ch = self.peek()
            if ch and ch.isalnum():
                s.append(ch)
                self.advance()
            else:
                break
        word = "".join(s)
        if word == "array":
            return Token(TokenKind.KW_ARRAY, word, start_line, start_col)
        if word == "var":
            return Token(TokenKind.KW_VAR, word, start_line, start_col)
        return Token(TokenKind.IDENT, word, start_line, start_col)

    def lex_hex(self):
        start_line, start_col = self.line, self.col
        if self.peek() != "0" or self.peek(2).lower() != "x":
            raise LexerError(f"Ожидалось hex число 0x... на позиции {self.line}:{self.col}")
        self.advance(2)
        digits = []
        while True:
            ch = self.peek()
            if ch and (ch.isdigit() or ch.lower() in "abcdef"):
                digits.append(ch)
                self.advance()
            else:
                break
        if not digits:
            raise LexerError(f"После 0x ожидались hex-цифры на позиции {self.line}:{self.col}")
        return Token(TokenKind.HEX, "".join(digits), start_line, start_col)

    def next_token(self):
        self.skip_ws()
        ch = self.peek()
        if ch == "":
            return Token(TokenKind.EOF, None, self.line, self.col)

        single = {
            "{": TokenKind.LBRACE,
            "}": TokenKind.RBRACE,
            ";": TokenKind.SEMI,
            "=": TokenKind.EQUAL,
            "(": TokenKind.LPAREN,
            ")": TokenKind.RPAREN,
            ",": TokenKind.COMMA,
            "?": TokenKind.QMARK,
            "[": TokenKind.LBRACKET,
            "]": TokenKind.RBRACKET,
        }
        if ch in single:
            tok = Token(single[ch], ch, self.line, self.col)
            self.advance()
            return tok

        if ch == "0" and self.peek(2).lower() == "x":
            return self.lex_hex()

        if ch.isalpha():
            return self.lex_ident_or_kw()

        raise LexerError(f"Неожиданный символ '{ch}' на позиции {self.line}:{self.col}")

    def tokenize(self):
        tokens = []
        while True:
            tok = self.next_token()
            tokens.append(tok)
            if tok.kind == TokenKind.EOF:
                break
        return tokens

# --------- AST (без конфликтов имён) ---------

class NumberNode:
    def __init__(self, value):
        self.value = value

class ArrayNode:
    def __init__(self, items):
        self.items = items

class DictItemNode:
    def __init__(self, key, value):
        self.key = key
        self.value = value

class MapNode:
    def __init__(self, items):
        self.items = items  # list of DictItemNode

class ConstRefNode:
    def __init__(self, name):
        self.name = name

class ConstDeclNode:
    def __init__(self, name, value):
        self.name = name
        self.value = value

class ProgramNode:
    def __init__(self, consts, root):
        self.consts = consts
        self.root = root

# --------- Парсер ---------

class ParseError(Exception):
    pass

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.i = 0

    def peek(self):
        return self.tokens[self.i]

    def advance(self):
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def expect(self, kind):
        tok = self.peek()
        if tok.kind != kind:
            raise ParseError(f"Ожидалось '{kind}' на {tok.line}:{tok.col}, найдено '{tok.kind}'")
        return self.advance()

    def parse_program(self):
        consts = []
        while self.peek().kind == TokenKind.KW_VAR:
            consts.append(self.parse_const_decl())
        root = self.parse_value()
        self.expect(TokenKind.EOF)
        return ProgramNode(consts, root)

    def parse_const_decl(self):
        self.expect(TokenKind.KW_VAR)
        ident = self.expect(TokenKind.IDENT)
        self.expect(TokenKind.EQUAL)
        val = self.parse_value()
        return ConstDeclNode(ident.value, val)

    def parse_value(self):
        t = self.peek()
        if t.kind == TokenKind.HEX:
            tok = self.advance()
            return NumberNode(int(tok.value, 16))
        if t.kind == TokenKind.KW_ARRAY:
            return self.parse_array()
        if t.kind == TokenKind.LBRACE:
            return self.parse_dict()
        if t.kind == TokenKind.QMARK:
            return self.parse_const_ref()
        raise ParseError(f"Ожидалось значение на {t.line}:{t.col}, найдено '{t.kind}'")

    def parse_array(self):
        self.expect(TokenKind.KW_ARRAY)
        self.expect(TokenKind.LPAREN)
        items = []
        if self.peek().kind != TokenKind.RPAREN:
            items.append(self.parse_value())
            while self.peek().kind == TokenKind.COMMA:
                self.advance()
                items.append(self.parse_value())
        self.expect(TokenKind.RPAREN)
        return ArrayNode(items)

    def parse_dict(self):
        self.expect(TokenKind.LBRACE)
        items = []
        while self.peek().kind != TokenKind.RBRACE:
            key_tok = self.expect(TokenKind.IDENT)
            self.expect(TokenKind.EQUAL)
            val = self.parse_value()
            self.expect(TokenKind.SEMI)
            items.append(DictItemNode(key_tok.value, val))
        self.expect(TokenKind.RBRACE)
        return MapNode(items)

    def parse_const_ref(self):
        self.expect(TokenKind.QMARK)
        self.expect(TokenKind.LBRACKET)
        name_tok = self.expect(TokenKind.IDENT)
        self.expect(TokenKind.RBRACKET)
        return ConstRefNode(name_tok.value)

# --------- Вычисление ---------

class EvalError(Exception):
    pass

class Evaluator:
    def __init__(self):
        self.consts = {}

    def eval_program(self, prog):
        for decl in prog.consts:
            if decl.name in self.consts:
                raise EvalError(f"Повторное объявление константы '{decl.name}'")
            val = self.eval_value(decl.value)
            self.consts[decl.name] = val
        return self.eval_value(prog.root)

    def eval_value(self, v):
        if isinstance(v, NumberNode):
            return v.value
        if isinstance(v, ArrayNode):
            return [self.eval_value(item) for item in v.items]
        if isinstance(v, MapNode):
            result = {}
            for item in v.items:
                result[item.key] = self.eval_value(item.value)
            return result
        if isinstance(v, ConstRefNode):
            if v.name not in self.consts:
                raise EvalError(f"Неизвестная константа '?[{v.name}]'")
            return self.consts[v.name]
        raise EvalError("Неизвестный тип значения")

# --------- Генерация TOML ---------

def emit_inline_table(dct):
    parts = []
    for k, v in dct.items():
        parts.append(f"{k} = {emit_value(v)}")
    return "{ " + ", ".join(parts) + " }"

def emit_value(v):
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(emit_value(x) for x in v) + "]"
    if isinstance(v, dict):
        return emit_inline_table(v)
    raise ValueError(f"Неподдерживаемый TOML тип: {type(v)}")

def emit_root(root):
    if isinstance(root, dict):
        lines = []
        for k, v in root.items():
            if isinstance(v, dict):
                lines.append(f"{k} = {emit_inline_table(v)}")
            else:
                lines.append(f"{k} = {emit_value(v)}")
        return ("\n".join(lines) + "\n") if lines else ""
    else:
        return f"value = {emit_value(root)}\n"

# --------- CLI ---------

def run_cli(argv=None):
    parser = argparse.ArgumentParser(
        description="Транслятор учебного конфигурационного языка в TOML"
    )
    parser.add_argument("-i", "--input", required=True, help="Путь к входному файлу")
    parser.add_argument("-o", "--output", required=True, help="Путь к выходному файлу")
    args = parser.parse_args(argv)

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            src = f.read()
    except OSError as e:
        print(f"Ошибка чтения входного файла: {e}", file=sys.stderr)
        return 2

    try:
        lx = Lexer(src)
        tokens = lx.tokenize()
        ps = Parser(tokens)
        prog = ps.parse_program()
        ev = Evaluator()
        root_val = ev.eval_program(prog)
        toml_text = emit_root(root_val)
    except (LexerError, ParseError) as e:
        print(f"Синтаксическая ошибка: {e}", file=sys.stderr)
        return 1
    except EvalError as e:
        print(f"Ошибка вычисления констант: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Внутренняя ошибка: {e}", file=sys.stderr)
        return 3

    try:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(toml_text)
    except OSError as e:
        print(f"Ошибка записи выходного файла: {e}", file=sys.stderr)
        return 2

    return 0

if __name__ == "__main__":
    sys.exit(run_cli())