# 00 考前練習環境：Docker、專案結構、常用指令（考場速查）

> 來源：`demo/README.md`（考前練習 README.pdf 內容相同）、`demo/Dockerfile`、演練試題 PDF「零、說明」；
> 外部連結：Docker Engine 安裝（Linux）、Docker Desktop（Windows / macOS）、Linux post-installation steps。

## 1. 演練文件說了什麼

- 考前練習**不是考題**，也不涉及考題演算法，不影響成績；目的是讓考生先熟悉背景知識與**考試當天的開發環境與作答流程**。
- 練習都能在自己的電腦完成，只需要 Docker、C 編譯器、make。
- 練習原始檔在出題的 repository 裡，各有自己的 `README.md`。

## 2. 專案結構與開始方式

```text
demo/
├── Dockerfile      建立練習環境的 image
├── .dockerignore   不放進 image 的檔案
├── README.md
├── section2-1/     用 ros2 CLI 觀察 node 與 topic（publisher.py、processor.py）
├── section2-2/     位元運算與 PIO 基礎（demo_asm.c、demo_pio.pio）
└── section2-3/     臨界區保護與資料搬運引擎（Makefile、critical-section/、transfer-engine/）
```

| 資料夾 | 內容 | 開始方式 |
|---|---|---|
| `section2-1/` | ros2 CLI 觀察 node、topic、訊息傳輸 | `python3 publisher.py`，要同時開三個終端機 |
| `section2-2/` | C 位元運算、一支最小的 PIO 範例（閱讀即可） | `cc demo_asm.c -o demo_asm && ./demo_asm` |
| `section2-3/` | pthread 臨界區、模擬的資料搬運引擎 | `make run` |

## 3. Docker 指令（都在 `demo/` 資料夾下執行）

```bash
docker run --rm hello-world                     # 確認 Docker 裝好：應看到 Hello from Docker!
docker build -t srecruit-demo .                 # 1. 建置 image（第一次或練習內容更新時；需要網路）
docker run --rm -it --name srecruit-demo srecruit-demo      # 2. 啟動 container，進入 /demo
docker exec -it srecruit-demo bash              # 3. 另開終端機進同一個 container（要幾個開幾個）
exit                                            # 4. 結束：第一個終端機離開時 container 停止並刪除，其他終端機一起中斷
```

| 情況 | 指令 |
|---|---|
| 要保留修改（掛載本機資料夾） | `docker run --rm -it --name srecruit-demo -v "$PWD:/demo" srecruit-demo` |
| 出現 `The container name "/srecruit-demo" is already in use` | 再開終端機用 `docker exec`；要重新開始先 `docker rm -f srecruit-demo` |
| Linux 出現 `permission denied` | 見下方 post-installation |
| 看執行中的 container | `docker ps` |
| 掛載裝置（例如板子的序列埠） | `docker run ... --device /dev/ttyUSB0 ...` 或 `-v /dev:/dev --privileged` |
| Docker 跑 micro-ROS agent | `docker run -it --rm -v /dev:/dev --privileged --net=host microros/micro-ros-agent:jazzy serial --dev /dev/ttyUSB0` |

**`--rm`**：結束後刪除 container（裡面的修改會消失）。**`-it`**：互動式終端機。**`--name`**：給 container 名字，`docker exec` 才找得到。**`-v 本機:容器`**：掛載資料夾。

## 4. Dockerfile 在做什麼

```dockerfile
ARG DEMO_BASE_IMAGE=ros:jazzy-ros-core          # 基底：ROS 2 Jazzy（可改成鏡像站）
FROM ${DEMO_BASE_IMAGE}
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev make \
    && rm -rf /var/lib/apt/lists/*
COPY . /demo
# 基底的 entrypoint 只幫第一個 shell source ROS；docker exec 會繞過它，所以寫進 .bashrc
RUN echo 'source /opt/ros/jazzy/setup.bash' >> /root/.bashrc
WORKDIR /demo
CMD ["bash"]
```

- 不含 pico-sdk、交叉編譯器、judge；不需要開發板、不需要 `--privileged`。
- Docker Hub 連不上時：`docker build --build-arg DEMO_BASE_IMAGE=<鏡像站>/ros:jazzy-ros-core -t srecruit-demo .`。
- 自己在別的 shell 用 ROS：`source /opt/ros/jazzy/setup.bash`。

## 5. 安裝 Docker（外部連結整理）

| 系統 | 方式 |
|---|---|
| Linux | **Docker Engine**。依發行版照官方步驟（Ubuntu、Debian、Fedora、CentOS、RHEL 等；Raspberry Pi OS 64 位用 Debian 的步驟，32 位有警告）。也有發行版自帶的套件與靜態 binary |
| Windows | **Docker Desktop**，在 **WSL 2** 中操作 |
| macOS | **Docker Desktop**（Apple 晶片或 Intel 各有安裝檔） |

**Linux post-installation：不用 sudo 執行 docker**

```bash
sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker                    # 或登出再登入
docker run hello-world           # 驗證
```

- 注意：`docker` 群組等於 **root 權限**。
- 之前用 sudo 跑過、出現 `~/.docker/config.json` permission denied：刪掉 `~/.docker/`，或 `sudo chown "$USER":"$USER" /home/"$USER"/.docker -R` 與 `sudo chmod g+rwx "$HOME/.docker" -R`。
- 開機自動啟動：`sudo systemctl enable docker.service` 與 `sudo systemctl enable containerd.service`（Debian / Ubuntu 預設就會）。

**Windows（WSL 2）**

- 需求：WSL 2.1.5 以上（`wsl --version`）；Windows 10 22H2（19045）或 Windows 11 23H2（22631）以上的 64 位 Home / Pro / Enterprise / Education；開啟 WSL 2 功能；BIOS 開啟硬體虛擬化；8 GB RAM。
- 安裝：執行 `Docker Desktop Installer.exe`，設定頁選「Use WSL 2 instead of Hyper-V」。命令列：`"Docker Desktop Installer.exe" install --user`（不需管理員）或 `install`（所有使用者）。
- 裝好後要手動開 Docker Desktop 並接受服務條款才會運作。
- 授權：個人、教育、非商業開源、小型企業（< 250 人且年營收 < 1000 萬美元）免費。

## 6. 考場可能用到的 Linux / git 指令

| 用途 | 指令 |
|---|---|
| 找序列埠 | `ls /dev/ttyUSB* /dev/ttyACM*`；`dmesg \| tail` |
| 序列埠權限 | `sudo usermod -aG dialout $USER`（重新登入） |
| 編譯 C（含檢查） | `gcc -std=c11 -O2 -Wall -Wextra x.c -o x`；除錯：`-g -fsanitize=address,undefined` |
| 多執行緒 | `gcc ... -pthread` |
| 看程式在哪裡當掉 | `gdb ./x` → `run` → `bt` |
| git | `git status`、`git add -A`、`git commit -m "Q1: ..."`、`git push`、`git log --oneline`、`git diff`、`git checkout -- 檔案`（放棄修改）、`git stash` |
| 背景執行 | `cmd &`；`jobs`；`kill %1` |
| 找字 | `grep -rn "關鍵字" .` |
