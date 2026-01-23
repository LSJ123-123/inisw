"use client";
import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

// 환경 변수 사용
const NGROK_URL = process.env.NGROK_URL_higan; 

interface Image {
    image_name: string;
    s3_url: string;
    uploaded_at: string;
}

const NewPage = () => {
    const [latestImage, setLatestImage] = useState<Image | null>(null);
    const [isAnalyzing, setIsAnalyzing] = useState(false); // 분석 중 상태 추가
    const router = useRouter();

    useEffect(() => {
        const fetchLatestImage = async () => {
            try {
                const response = await fetch("/api/latest-image");
                if (!response.ok) {
                    throw new Error("Failed to fetch latest image");
                }
                const result = await response.json();
                setLatestImage(result.image);
            } catch (error) {
                console.error(error);
            }
        };

        fetchLatestImage();
    }, []);

    // 서버 작업 상태 확인용 공통 폴링 함수
    const pollTaskStatus = async (taskId: string): Promise<any> => {
        return new Promise((resolve, reject) => {
            const interval = setInterval(async () => {
                try {
                    const response = await fetch(`${NGROK_URL}/task_status/${taskId}`, {
                        headers: { "ngrok-skip-browser-warning": "69420" },
                    });
                    const data = await response.json();

                    if (data.status === "completed") {
                        clearInterval(interval);
                        resolve(data.result);
                    } else if (data.status === "failed") {
                        clearInterval(interval);
                        reject(new Error(data.error || "Task failed"));
                    }
                } catch (err) {
                    clearInterval(interval);
                    reject(err);
                }
            }, 3000);
        });
    };

    const handleViewRecommendation = async () => {
        try {
            setIsAnalyzing(true); // 로딩 시작

            // Step 1: Flask 서버 호출 (비동기 Task 시작)
            const flaskResponse = await fetch(`${NGROK_URL}/run-higan`, {
                method: "POST",
                headers: { 
                    "Content-Type": "application/json",
                    "ngrok-skip-browser-warning": "69420",
                },
                body: JSON.stringify({ image_url: latestImage?.s3_url }) // 필요 시 바디 추가
            });

            if (!flaskResponse.ok) {
                const error = await flaskResponse.json();
                console.error("Flask 서버 호출 실패:", error.error || "알 수 없는 오류");
                alert("추천 위치 분석 요청에 실패했습니다.");
                return;
            }

            // Task ID를 받아 폴링 시작
            const { task_id } = await flaskResponse.json();
            const flaskData = await pollTaskStatus(task_id);
            console.log("Flask 실행 결과 (완료):", flaskData);

            // Step 2: 기존 좌표 및 쿼리 생성 로직
            const coordinates = { x: 210, y: 145 }; // 임의 좌표 (flaskData에서 받아올 수도 있음)
            const query = new URLSearchParams({
                imageUrl: latestImage?.s3_url || "",
                x: coordinates.x.toString(),
                y: coordinates.y.toString(),
            }).toString();

            // Step 3: 기존 URL 이동 로직
            router.push(`/location?${query}`);
        } catch (error) {
            console.error("추천 위치 보기 처리 실패:", error);
            alert("추천 위치 처리가 실패했습니다.");
        } finally {
            setIsAnalyzing(false); // 로딩 종료
        }
    };

    return (
        <div className="bg-black flex flex-col min-h-screen">
            <div className="flex justify-center">
                <Navbar backgroundColor="rgb(0, 0, 0)" />
            </div>

            <div className="flex flex-grow justify-center items-center mt-10">
                {latestImage ? (
                    <div className="mb-20 bg-white rounded-lg shadow-md p-6 text-center w-[320px]">
                        <img
                            src={latestImage.s3_url}
                            alt={latestImage.image_name}
                            className="w-full h-[300px] object-cover rounded-md"
                        />
                        <p className="mt-3 text-gray-800 font-custom">
                            업로드된 이미지
                        </p>
                        <button
                            onClick={handleViewRecommendation}
                            disabled={isAnalyzing} // 분석 중일 때 버튼 비활성화
                            className={`group mt-5 px-5 py-2 rounded-lg transition-colors ${
                                isAnalyzing ? "bg-gray-400 cursor-not-allowed" : "bg-gray-700 hover:bg-[#ECD77F]"
                            }`}
                        >
                            <p className={`font-second ${isAnalyzing ? "text-gray-200" : "text-white group-hover:text-black"}`}>
                                {isAnalyzing ? "분석 중..." : "추천 위치 보기"}
                            </p>
                        </button>
                    </div>
                ) : (
                    <p className="text-white">이미지가 없습니다. 업로드를 시도해주세요.</p>
                )}
            </div>
            <Footer />
        </div>
    );
};

export default NewPage;