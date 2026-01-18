"use client";
import { useState } from "react";

interface ImageUploaderProps {
  onImageUpload: (imageInfo: { name: string; url: string }) => void;
}

const ImageUploader = ({ onImageUpload }: ImageUploaderProps) => {
  const [isDragging, setIsDragging] = useState(false);

  const handleFile = async (file: File) => {
    if (!file.type.startsWith("image/")) {
      alert("이미지 파일만 업로드 가능합니다.");
      return;
    }

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      const text = await response.text(); // 항상 text로 먼저 읽기
      let result: any;

      try {
        result = JSON.parse(text); // JSON 파싱 시도
      } catch {
        console.error("서버가 JSON이 아닌 데이터를 반환했습니다:", text);
        alert("서버 오류 발생:\n" + text);
        return;
      }

      if (response.ok) {
        if (onImageUpload) {
          onImageUpload({
            name: result.image.name,
            url: result.image.url,
          });
        }
        // 페이지 이동
        window.location.href = "/newpage";
      } else {
        alert(result.error || "업로드 중 오류가 발생했습니다.");
      }
    } catch (error) {
      console.error("이미지 업로드 중 오류:", error);
      alert("이미지 업로드에 실패했습니다.");
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  return (
    <div className="relative w-full h-[45vh] flex justify-center items-center">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`w-[400px] h-[150px] flex justify-center items-center bg-gray-800 rounded-lg p-5 cursor-pointer ${
          isDragging ? "border-2 border-black" : "border-2 border-gray-400"
        }`}
      >
        <input
          type="file"
          accept="image/*"
          onChange={handleFileChange}
          className="hidden"
          id="fileInput"
        />
        <label
          htmlFor="fileInput"
          className="cursor-pointer flex flex-col justify-center items-center text-center"
        >
          <span className="font-second text-white text-[17px]">
            인테리어 이미지를 업로드하세요.
          </span>
          <img
            src="/images/upload.png"
            alt="업로드 아이콘"
            className="w-[48px] h-[48px] mt-2"
          />
        </label>
      </div>
    </div>
  );
};

export default ImageUploader;
