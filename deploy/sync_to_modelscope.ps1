<#
  把项目同步到魔搭创空间仓库（只复制代码，不覆盖平台生成的配置文件）

  用法：
     powershell -ExecutionPolicy Bypass -File deploy\sync_to_modelscope.ps1 -SpaceDir "C:\Users\Lenovo\Documents\ms-space"

  它做三件事：
     1. 复制运行需要的文件和目录
     2. 清理 __pycache__
     3. 明确告诉你：没有覆盖 README.md（平台配置可能在里面）

  之后你自己 cd 进空间目录，git add / commit / push
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$SpaceDir
)

$ErrorActionPreference = 'Stop'
$src = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path $SpaceDir)) {
    throw "目标目录不存在：$SpaceDir`n请先 git clone 创空间仓库到这个路径"
}

# 需要同步的内容（故意不包含 README.md / .gitignore / .git）
$items = @(
    'Dockerfile',
    'requirements-serve.txt',
    'src',
    'models',
    'data',
    'docs',
    'scripts'
)

Write-Host "源目录: $src"
Write-Host "目标:   $SpaceDir"
Write-Host ""

foreach ($i in $items) {
    $p = Join-Path $src $i
    if (Test-Path $p) {
        Copy-Item -Path $p -Destination $SpaceDir -Recurse -Force
        Write-Host "  [复制] $i"
    }
    else {
        Write-Host "  [跳过] $i（不存在）" -ForegroundColor DarkGray
    }
}

# 清理缓存，避免把 .pyc 推上去
$pycache = Get-ChildItem -Path $SpaceDir -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue
if ($pycache) {
    $pycache | Remove-Item -Recurse -Force
    Write-Host "  [清理] __pycache__ ($($pycache.Count) 个)"
}

Write-Host ""
Write-Host "同步完成。" -ForegroundColor Green
Write-Host "注意：README.md 没有被覆盖（如果平台把配置写在这里，保留它）" -ForegroundColor Yellow
Write-Host ""
Write-Host "接下来在空间目录里执行：" -ForegroundColor Cyan
Write-Host "  cd `"$SpaceDir`""
Write-Host "  git status              # 先看清楚要提交什么"
Write-Host "  git add ."
Write-Host "  git commit -m `"deploy: 首次部署 campus-repair-triage`""
Write-Host "  git push"
Write-Host ""
Write-Host "推送前最后确认一次：Dockerfile 在仓库根目录，且里面 --port 与平台要求一致" -ForegroundColor Yellow
