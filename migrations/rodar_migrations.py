#!/usr/bin/env python3
"""
Script para rodar as migrations do Supabase.
Execute dentro do container: docker compose exec backend python3 migrations/rodar_migrations.py
Ou manualmente: copie cada arquivo .sql no SQL Editor do Supabase.
"""

import os
import sys

def main():
    migration_dir = os.path.dirname(__file__)
    sql_files = sorted([
        f for f in os.listdir(migration_dir)
        if f.endswith('.sql')
    ])

    if not sql_files:
        print("Nenhum arquivo .sql encontrado em migrations/")
        return

    print("=" * 60)
    print("MIGRATIONS DO LEADFLOW")
    print("=" * 60)
    print()
    print("Cole cada SQL abaixo no Supabase SQL Editor:")
    print("supabase.com → seu projeto → SQL Editor → New Query")
    print()

    for f in sql_files:
        path = os.path.join(migration_dir, f)
        with open(path) as fp:
            content = fp.read()
        print(f"{'─'*60}")
        print(f"Arquivo: {f}")
        print(f"{'─'*60}")
        print(content[:200] + "..." if len(content) > 200 else content)
        print()

    print("=" * 60)
    print(f"Total: {len(sql_files)} migrations")
    print("Ordem de execução:", ", ".join(sql_files))

if __name__ == "__main__":
    main()
