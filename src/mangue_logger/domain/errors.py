"""Exceções do domínio. Nenhuma camada interna depende de Qt para sinalizar erro."""

from __future__ import annotations


class MangueLoggerError(Exception):
    """Base de todos os erros esperados da aplicação."""


class ValidationError(MangueLoggerError, ValueError):
    """Parâmetro ou arquivo de configuração inválido."""


class ReaderError(MangueLoggerError):
    """Falha ao ler/interpretar um arquivo de run."""


class ExpressionError(ValidationError):
    """Expressão de canal virtual inválida ou insegura."""
