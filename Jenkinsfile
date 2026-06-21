// =============================================================================
// Superset 性能测试 — Jenkinsfile
// 镜像 .github/workflows/perf.yml，分三档：pr-gate / nightly / release
//
// 使用方法：
//   1. Jenkins → New Item → Pipeline → "superset-perf"
//   2. Pipeline script from SCM → 指向本仓库，Script Path = Jenkinsfile
//   3. Build with Parameters 选择 MODE / SUPERSET_VERSION / DURATION_MIN
//   4. (可选) 配置 GitHub / GitLab webhook 触发 pr-gate
// =============================================================================

pipeline {
    agent {
        // 推荐：专用的 perf agent（独立机器，避免与 Superset 容器争资源）
        label 'perf-runner && linux && docker'
    }

    options {
        // nightly / release 单次最长 2 小时
        timeout(time: 2, unit: 'HOURS')
        // 不并发跑同一 MODE（保护 Superset 容器）
        disableConcurrentBuilds()
        // 输出带时间戳
        timestamps()
        // 保留 30 个构建
        buildDiscarder(logRotator(numToKeepStr: '30', artifactNumToKeepStr: '10'))
    }

    parameters {
        choice(
            name: 'MODE',
            choices: ['pr-gate', 'nightly', 'release', 'smoke'],
            description: '压测档位：pr-gate=轻量门禁 / nightly=标准 / release=大压 / smoke=最小'
        )
        choice(
            name: 'SUPERSET_VERSION',
            choices: ['6.0', '4.1', 'both'],
            description: '压测目标版本（pr-gate 仅 6.0，release/nightly 可 both）'
        )
        string(
            name: 'DURATION_MIN',
            defaultValue: '10',
            description: 'Locust 持续时间（分钟），仅 nightly/release 生效'
        )
        string(
            name: 'USERS',
            defaultValue: '200',
            description: 'Locust 并发用户数'
        )
    }

    environment {
        REPO_ROOT = "${env.WORKSPACE}"
        E2E_DIR   = "${env.WORKSPACE}/e2e"
        PYTHON    = 'python3'
        // 抑制 Locust 在 Windows 上读 pyproject.toml 的 GBK 报错（agent 是 Linux 时可忽略）
        PYTHONUTF8 = '1'
        PYTHONIOENCODING = 'utf-8'
    }

    stages {

        // ---------------------------------------------------------------------
        // 0. 环境准备：拉代码、装 Python / k6 / Locust、起 Superset
        // ---------------------------------------------------------------------
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git rev-parse --short HEAD > .git/short_sha'
                sh 'cat .git/short_sha'
            }
        }

        stage('Install deps') {
            steps {
                sh '''
                    set -e
                    sudo apt-get update
                    sudo apt-get install -y python3-pip python3-venv

                    # k6
                    sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 \
                        --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
                    echo "deb https://dl.k6.io/deb stable main" | \
                        sudo tee /etc/apt/sources.list.d/k6.list
                    sudo apt-get update
                    sudo apt-get install -y k6
                    k6 version

                    # Python deps
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --upgrade pip
                    pip install -r e2e/requirements.txt -r e2e/perf/requirements.txt
                '''
            }
        }

        stage('Start Superset') {
            steps {
                script {
                    def versions = params.SUPERSET_VERSION == 'both' ? ['4.1', '6.0'] : [params.SUPERSET_VERSION]
                    versions.each { v ->
                        sh """
                            cd superset-${v}
                            docker compose up -d
                            docker compose ps
                        """
                    }
                }
            }
        }

        stage('Wait healthy') {
            steps {
                sh '''
                    . .venv/bin/activate
                    python3 e2e/perf/tools/wait_healthy.py \
                        --versions ${SUPERSET_VERSION == 'both' ? '4.1,6.0' : SUPERSET_VERSION} \
                        --timeout 300
                '''
            }
        }

        // ---------------------------------------------------------------------
        // 1. 元测试（必跑，保护阈值/基线/配置不回退）
        // ---------------------------------------------------------------------
        stage('Meta tests') {
            steps {
                sh '''
                    . .venv/bin/activate
                    cd e2e
                    python3 -m pytest perf/tests/ -v
                '''
            }
        }

        // ---------------------------------------------------------------------
        // 2. 压测主体：按 MODE 走不同流程
        // ---------------------------------------------------------------------
        stage('Run perf') {
            parallel {
                // ---- PR gate：仅 6.0 + 两个重点 k6 ----
                stage('PR gate (k6 dashboard_list + chart_list)') {
                    when { expression { params.MODE == 'pr-gate' || params.MODE == 'smoke' } }
                    steps {
                        sh '''
                            . .venv/bin/activate
                            cd e2e
                            SUPERSET_URL=http://localhost:18089 \
                                VUS=300 DURATION=3m \
                                bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_list.js
                            SUPERSET_URL=http://localhost:18089 \
                                VUS=200 DURATION=2m \
                                bash perf/tools/run_k6.sh perf/k6/scripts/chart_list.js
                        '''
                    }
                }

                // ---- Nightly：Locust 10 min × 版本 + 重点 k6 全部 ----
                stage('Locust 4.1') {
                    when {
                        expression {
                            params.MODE == 'nightly' || params.MODE == 'release'
                        }
                        expression { params.SUPERSET_VERSION == '4.1' || params.SUPERSET_VERSION == 'both' }
                    }
                    steps {
                        sh '''
                            . .venv/bin/activate
                            cd e2e
                            PERF_TARGET_VERSION=4.1 \
                            DURATION_MIN=${DURATION_MIN} USERS=${USERS} \
                                bash perf/tools/run_locust.sh
                        '''
                    }
                }

                stage('Locust 6.0') {
                    when {
                        expression {
                            params.MODE == 'nightly' || params.MODE == 'release'
                        }
                        expression { params.SUPERSET_VERSION == '6.0' || params.SUPERSET_VERSION == 'both' }
                    }
                    steps {
                        sh '''
                            . .venv/bin/activate
                            cd e2e
                            PERF_TARGET_VERSION=6.0 \
                            DURATION_MIN=${DURATION_MIN} USERS=${USERS} \
                                bash perf/tools/run_locust.sh
                        '''
                    }
                }

                stage('k6 chart_data (5 min)') {
                    when { expression { params.MODE == 'nightly' || params.MODE == 'release' } }
                    steps {
                        sh '''
                            . .venv/bin/activate
                            cd e2e
                            SUPERSET_URL=http://localhost:18089 \
                                VUS=100 DURATION=5m \
                                bash perf/tools/run_k6.sh perf/k6/scripts/chart_data.js
                        '''
                    }
                }

                stage('k6 dashboard_detail (3 min)') {
                    when { expression { params.MODE == 'nightly' || params.MODE == 'release' } }
                    steps {
                        sh '''
                            . .venv/bin/activate
                            cd e2e
                            SUPERSET_URL=http://localhost:18089 \
                                VUS=200 DURATION=3m \
                                bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_detail.js
                        '''
                    }
                }

                stage('k6 dashboard_render (3 min)') {
                    when { expression { params.MODE == 'nightly' || params.MODE == 'release' } }
                    steps {
                        sh '''
                            . .venv/bin/activate
                            cd e2e
                            SUPERSET_URL=http://localhost:18089 \
                                VUS=150 DURATION=3m \
                                bash perf/tools/run_k6.sh perf/k6/scripts/dashboard_render.js
                        '''
                    }
                }
            }
        }

        // ---------------------------------------------------------------------
        // 3. 对比基线（nightly/release 必跑，pr-gate 跳过因为没有 baseline 对比目标）
        // ---------------------------------------------------------------------
        stage('Compare vs baseline') {
            when { expression { params.MODE == 'nightly' || params.MODE == 'release' } }
            steps {
                script {
                    def versions = params.SUPERSET_VERSION == 'both' ? ['4.1', '6.0'] : [params.SUPERSET_VERSION]
                    versions.each { v ->
                        sh """
                            . .venv/bin/activate
                            cd e2e
                            python3 perf/tools/compare_baseline.py \\
                                --version ${v} \\
                                --current perf/reports/locust/current_${v}.json \\
                                --strict \\
                                --exit-on-fail
                        """
                    }
                }
            }
        }

        // ---------------------------------------------------------------------
        // 4. 采集容器资源（可选，但 nightly/release 建议开）
        // ---------------------------------------------------------------------
        stage('Collect docker stats') {
            when { expression { params.MODE == 'nightly' || params.MODE == 'release' } }
            steps {
                script {
                    def versions = params.SUPERSET_VERSION == 'both' ? ['4.1', '6.0'] : [params.SUPERSET_VERSION]
                    versions.each { v ->
                        sh """
                            . .venv/bin/activate
                            python3 e2e/perf/tools/collect_docker_stats.py \\
                                --containers superset-${v}-web,superset-${v}-postgres,superset-${v}-redis \\
                                --out e2e/perf/reports/locust/docker_stats_${v}.csv \\
                                --interval 2 \\
                                --duration $((DURATION_MIN.toInteger() * 60 + 60)) &
                        """
                    }
                    // 等 Locust 结束
                    sh 'sleep 5'
                }
            }
        }
    }

    // -------------------------------------------------------------------------
    // post：无论成败都跑
    // -------------------------------------------------------------------------
    post {
        always {
            // 收报告
            archiveArtifacts artifacts: '''
                e2e/perf/reports/locust/**/*,
                e2e/perf/reports/k6/**/*,
                e2e/perf/reports/**/docker_stats*.csv
            ''', allowEmptyArchive: true, fingerprint: true

            // 打印 summary
            sh '''
                . .venv/bin/activate
                cd e2e
                echo "=========================== LOCUST SUMMARY ==========================="
                for f in perf/reports/locust/summary_*.txt; do
                    if [ -f "$f" ]; then
                        echo "---- $f ----"
                        cat "$f"
                    fi
                done
            '''
        }

        success {
            echo '✅ perf pipeline passed'
        }

        failure {
            echo '❌ perf pipeline failed — check archiveArtifacts for reports'
        }

        unstable {
            echo '⚠️ perf pipeline unstable — baseline violations present'
        }

        cleanup {
            // 关 Superset 容器
            sh '''
                cd superset-4.1 && docker compose down 2>/dev/null || true
                cd ../superset-6.0 && docker compose down 2>/dev/null || true
            '''
            // 清 venv
            sh 'rm -rf .venv'
        }
    }
}
