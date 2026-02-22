---
description: Detect the project's ORM/migration tool and run migrations
allowed-tools: [Bash, Read, Glob, Grep]
---

# Migrate

Detect the project's migration tooling and run migrations.

## Instructions

1. **Detect the migration tool** by reading `CLAUDE.md` and scanning the project:
   - Django → `python manage.py makemigrations` + `python manage.py migrate`
   - TypeORM → `typeorm migration:generate` + `typeorm migration:run` (or project scripts)
   - Prisma → `prisma migrate dev`
   - Drizzle → `drizzle-kit generate` + `drizzle-kit migrate`
   - Sequelize → `sequelize-cli db:migrate`
   - Knex → `knex migrate:latest`
   - Rails → `rails db:migrate`
   - Other → check `package.json` scripts or project docs for migration commands

2. **Show what will be migrated** (generate/preview step) and present to the user

3. **Run the migration** only with user approval

If the project's migration tool cannot be detected, ask the user.

## Arguments

$ARGUMENTS
