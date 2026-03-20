-- Tabela de histórico de conversas do agente IA
-- Execute no Supabase SQL Editor

create table if not exists conversas (
  id         uuid primary key default gen_random_uuid(),
  empresa_id uuid not null references empresas(id) on delete cascade,
  telefone   text not null,
  role       text not null check (role in ('user', 'assistant')),
  conteudo   text not null,
  criado_em  timestamptz not null default now()
);

create index if not exists conversas_empresa_telefone_idx
  on conversas (empresa_id, telefone, criado_em);

-- RLS: apenas service_role acessa (backend usa service key)
alter table conversas enable row level security;
