<#
.SYNOPSIS
    Sincroniza a app principal com o clone de deploy do Hugging Face Space
    e (opcionalmente) faz commit + push.

.DESCRIPTION
    Copia apenas o que e partilhado entre o projeto e o Space:
        - app/        (codigo do dashboard + assets)
        - config.py   (parametros do sistema)
        - data/processed/mobilidade.db  (modelo ja construido)

    NAO toca em ficheiros especificos do deploy:
        - Dockerfile, requirements.txt, README.md  (configuracao de producao)
        - .git/, .gitattributes

    Depois mostra o git status do Space. Use -Push para fazer commit + push
    automaticamente para o Hugging Face.

.EXAMPLE
    .\sincronizar_deploy.ps1
        So copia os ficheiros e mostra o que mudou (nao faz push).

.EXAMPLE
    .\sincronizar_deploy.ps1 -Push -Mensagem "Atualiza calculo do IIC"
        Copia, faz commit com a mensagem dada e push para o Space.
#>

param(
    [switch]$Push,
    [string]$Mensagem = "Sincroniza app com o projeto principal"
)

$ErrorActionPreference = "Stop"

# Raiz do projeto = pasta deste script.
$Raiz = $PSScriptRoot

# Pasta do clone de deploy. Aceita o nome novo e o antigo, para o caso de o
# rename ainda nao ter sido feito.
$Deploy = $null
foreach ($nome in @("deploy-huggingface", "Dashboard-MobilidadeUrbana-Lisboa")) {
    $candidato = Join-Path $Raiz $nome
    if (Test-Path $candidato) { $Deploy = $candidato; break }
}

if (-not $Deploy) {
    throw "Pasta de deploy nao encontrada (deploy-huggingface/ ou Dashboard-MobilidadeUrbana-Lisboa/) em $Raiz"
}

Write-Host "==> A sincronizar para: $Deploy" -ForegroundColor Cyan

# 1. app/  -> espelha o codigo, excluindo caches do Python.
#    /MIR mantem o destino igual a origem; /XD exclui pastas __pycache__.
$origemApp  = Join-Path $Raiz   "app"
$destinoApp = Join-Path $Deploy "app"
robocopy $origemApp $destinoApp /MIR /XD "__pycache__" /NFL /NDL /NJH /NJS /NP | Out-Null
Write-Host "    [ok] app/" -ForegroundColor Green

# 2. config.py
Copy-Item (Join-Path $Raiz "config.py") (Join-Path $Deploy "config.py") -Force
Write-Host "    [ok] config.py" -ForegroundColor Green

# 3. Base de dados construida (so se existir).
$bdOrigem  = Join-Path $Raiz   "data\processed\mobilidade.db"
$bdDestino = Join-Path $Deploy "data\processed\mobilidade.db"
if (Test-Path $bdOrigem) {
    Copy-Item $bdOrigem $bdDestino -Force
    Write-Host "    [ok] data/processed/mobilidade.db" -ForegroundColor Green
} else {
    Write-Host "    [aviso] mobilidade.db nao existe na origem; corre 'python construir_modelo.py' primeiro." -ForegroundColor Yellow
}

# 4. Estado do repositorio do Space.
Push-Location $Deploy
try {
    Write-Host "`n==> Alteracoes no repositorio do Space:" -ForegroundColor Cyan
    git status --short

    if ($Push) {
        $alteracoes = git status --porcelain
        if ([string]::IsNullOrWhiteSpace($alteracoes)) {
            Write-Host "`nNada para enviar: o Space ja esta atualizado." -ForegroundColor Yellow
        } else {
            Write-Host "`n==> commit + push para o Hugging Face..." -ForegroundColor Cyan
            git add -A
            git commit -m $Mensagem
            git push origin main
            Write-Host "[ok] Space atualizado." -ForegroundColor Green
        }
    } else {
        Write-Host "`n(Modo pre-visualizacao: nada foi enviado.)" -ForegroundColor DarkGray
        Write-Host "Para publicar: .\sincronizar_deploy.ps1 -Push -Mensagem `"a tua mensagem`"" -ForegroundColor DarkGray
    }
}
finally {
    Pop-Location
}
